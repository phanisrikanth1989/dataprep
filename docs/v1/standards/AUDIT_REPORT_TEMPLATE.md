# Gold Standard: Audit Report Template

> Reference: tFileInputDelimited.md and tMap.md (best existing examples)
> Methodology: docs/v1/standards/METHODOLOGY.md (scoring framework, checklists, review process)

Every component audit report MUST follow this exact section structure. No sections may be omitted — use "N/A" or "None" if a section has no content.

---

## Purpose of Audit Reports

These reports serve dual purpose:

1. **Now**: Task prioritization for production readiness — what's broken, what order to fix
2. **Later**: Production documentation — how the component works, known limitations

Reports are maintained as a living document. When issues are fixed, they stay in the report with strikethrough status (see Issue Convention below).

---

## Issue Convention

**Resolved issues stay in the report** with strikethrough and status:
```
| CONV-FID-001 | ~~P1~~ | **FIXED** — Now has dedicated converter class in talend_to_v1 |
| CONV-FID-004 | **P1** | **OPEN — DEFERRED** — Cross-cutting type mapping issue |
| ENG-MAP-003  | ~~P2~~ | **SUPERSEDED** — Replaced by talend_to_v1 converter pipeline |
```

Valid statuses: **OPEN**, **FIXED**, **SUPERSEDED**, **DEFERRED** (with reason)

At a glance: **bold = needs attention**, ~~strikethrough~~ = done.

---

## Priority Definitions

| Priority | Label | Definition | Action Required |
| ---------- | ------- | ------------ | ----------------- |
| **P0** | Critical | Causes incorrect results, data loss, runtime crash, or blocks production use | Must fix before any production migration |
| **P1** | Major | Significant feature gap or behavioral difference vs Talend. Likely hit in real jobs | Fix before production migration of affected jobs |
| **P2** | Moderate | Minor feature gap, edge case, cosmetic issue, naming inconsistency, or standards violation | Fix during hardening phase |
| **P3** | Low | Enhancement, optimization, code cleanup, or nice-to-have. Does not affect correctness | Fix when time permits |

---

## Scoring

| Score | Meaning |
| ------- | --------- |
| **R (Red)** | Broken, missing, or will produce wrong results |
| **Y (Yellow)** | Partially works, gaps exist, needs attention |
| **G (Green)** | Works correctly, meets standards |
| **N/A** | Not applicable to this component |

---

## Two-Pass Review Process

From METHODOLOGY.md — every audit goes through:

### Pass 1: Initial Audit

- Research Talend documentation online (.item files + _java.xml from Talaxie GitHub)
- Read the v1 engine implementation (every line)
- Read the converter code (dispatch + parser + parameter mapping)
- Write the full audit report following this template

### Pass 2: Adversarial Review

- A separate reviewer reads the report AND the source code
- Mindset: "Find at least 3-5 issues the report missed"
- Focuses on edge cases, cross-class interactions, behavioral subtleties
- Findings incorporated back into the report before commit

---

## Mandatory Edge-Case Checklist

Every audit MUST check these cross-cutting concerns (from METHODOLOGY.md):

| Check | Why |
| ------- | ----- |
| NaN handling (`pd.isna()` vs `is None`) | pandas uses NaN, not None — `value is None` misses NaN |
| Empty strings in config keys | Can produce crashes (e.g., `str.split("")` raises ValueError) |
| Empty DataFrame input (0 rows with columns vs None) | Returning `pd.DataFrame()` loses column schema |
| HYBRID streaming mode via base class | Base class chunks and calls `_process()` per chunk — stateful components break |
| `_update_global_map()` crash effect | Crashes ALL components when globalMap is set |
| Type demotion through iterrows/Series reconstruction | `Decimal` → `float64`, `datetime64` → `object` |
| `validate_schema` nullable logic (inverted) | `nullable=True` triggers `fillna(0)` — should be the opposite |
| `_validate_config()` called or dead code | Most components define it but never call it |

---

## Template

```markdown
# Audit Report: {TalendName} / {V1EngineClassName}

> **Audited**: {date}
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** — this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `{tComponentName}` |
| **V1 Engine Class** | `{EngineClassName}` |
| **Engine File** | `src/v1/engine/components/{category}/{file}.py` ({N} lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/{category}/{file}.py` ({N} lines) |
| **Converter Dispatch** | `@REGISTRY.register("{tComponentName}")` decorator-based dispatch |
| **Registry Aliases** | `{EngineClassName}`, `{tComponentName}` |
| **Category** | {Category} / {SubCategory} |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/{...}` | Engine implementation ({N} lines) |
| `src/converters/talend_to_v1/components/{...}` | Converter class ({N} lines) |
| `tests/converters/talend_to_v1/components/test_{...}.py` | Converter tests ({N} tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **{R/Y/G}** | {n} | {n} | {n} | {n} | {Brief: X of Y params extracted, needs_review count} |
| Engine Feature Parity | **{R/Y/G}** | {n} | {n} | {n} | {n} | {Brief: key gaps} |
| Code Quality | **{R/Y/G}** | {n} | {n} | {n} | {n} | {Brief: cross-cutting bugs, naming, standards} |
| Performance & Memory | **{R/Y/G}** | {n} | {n} | {n} | {n} | {Brief: streaming, anti-patterns} |
| Testing | **{R/Y/G}** | {n} | {n} | {n} | {n} | {Brief: test count, coverage} |

**Overall: {COLOR} — {One-line assessment}**

**Top Actions**: {3-5 most important fixes needed, or "Production ready" if all Green}

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH — researched from .item files, _java.xml, and official docs.

### What {tComponentName} Does

{2-3 paragraph description. Written for someone unfamiliar with Talend. Include typical use cases.}

**Source**: {URLs to official Talend docs, Talaxie GitHub, community resources}
**Component family**: {Family} / {SubFamily}
**Available in**: {Talend product variants}
**Required JARs**: {List or "None (built-in)"}

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | {Human name} | `{XML_NAME}` | {Type} | {default} | {Description with behavioral notes} |

### 3.2 Advanced Settings

{Same table format. Include only if component has advanced settings.}

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | {Description} |
| `REJECT` | Output | Row > Reject | {Description with errorCode/errorMessage columns note} |
| `SUBJOB_OK` | Output (Trigger) | Trigger | {Description} |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | {Description} |

### 3.5 Behavioral Notes

{Numbered list of important behavioral details:

- Non-obvious defaults (e.g., ISO-8859-15 not UTF-8)
- Common gotchas
- Parameter interactions
- Edge cases
}

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

{Brief description of converter architecture and flow.}

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `{PARAM_NAME}` | Yes/No | `{config_key}` | {Notes including default value} |

**Summary**: {X} of {Y} parameters extracted ({Z}%).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | {How} |
| `type` | Yes | {How — note any conversion from Talend types} |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | |
| `precision` | Yes | |
| `pattern` | Yes | {Java-to-Python date pattern conversion} |
| `default` | No | {Why not} |

### 4.3 Expression Handling

{How context variables (`context.var`) and Java expressions (`{{java}}`) are handled.}

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-{ID}-001 | **P{N}** | {Description — OPEN/FIXED/SUPERSEDED/DEFERRED} |

### 4.5 Needs Review Entries

{All needs_review entries the converter emits for engine gaps.}

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `{key}` | {Why this is an engine gap} | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | {Feature} | **Yes/No/Partial** | High/Medium/Low/N/A | `{method}` line {N} | {Notes} |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-{ID}-001 | **P{N}** | {Detailed description} |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_{VAR}` | Yes | Yes/No/Partial | {Method} | {Notes} |

{For complex components like tMap, add:}

### 5.4 Architecture Overview (optional — for complex components)

{Execution flow, multi-input handling, Java bridge interaction, etc.}

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-{ID}-001 | **P{N}** | `{file}:{line}` | {Description. Note CROSS-CUTTING if applicable.} |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-{ID}-001 | **P{N}** | {Description} |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-{ID}-001 | **P{N}** | "{Standard rule}" | {How violated} |

### 6.4 Debug Artifacts

{Leftover debug code, print statements, TODO comments. Or "None found."}

### 6.5 Security

{Security concerns — path traversal, exec/eval, injection. Or "No concerns identified."}

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | {Assessment} |
| Level usage | {Assessment} |
| Sensitive data | {Assessment} |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | {Assessment} |
| Exception chaining | {Assessment} |
| die_on_error handling | {Assessment} |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | {Assessment} |
| Parameter types | {Assessment} |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-{ID}-001 | **P{N}** | {Description} |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | {Assessment} |
| Memory threshold | {Assessment} |
| Large data handling | {Assessment} |

{For complex components, add streaming mode limitations, chunked execution edge cases, etc.}

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | {N} | `tests/converters/talend_to_v1/components/test_{name}.py` |
| Engine unit tests | {N} | {Location or "None"} |
| Integration tests | {N} | {Location or "None"} |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-{ID}-001 | **P{N}** | {What's not tested} |

### 8.3 Recommended Test Cases

{List specific test scenarios that should be added. Focus on:

- Happy path with realistic data
- Edge cases (empty input, nulls, encoding)
- Error paths (die_on_error=True/False)
- Schema enforcement
- Large data / streaming
}

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | {N} | {List — bold for OPEN, strikethrough for resolved} |
| P1 | {N} | {List} |
| P2 | {N} | {List} |
| P3 | {N} | {List} |
| **Total** | **{N}** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | {N} | {List} |
| Engine (ENG) | {N} | {List} |
| Bug (BUG) | {N} | {List} |
| Naming (NAME) | {N} | {List} |
| Standards (STD) | {N} | {List} |
| Performance (PERF) | {N} | {List} |
| Testing (TEST) | {N} | {List} |

### Cross-Cutting Issues

{Issues shared with other components. Reference canonical IDs from CROSS_CUTTING_ISSUES.md or other reports.}

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)
{P0 + critical P1 issues that block production use}

### Short-term (Hardening)
{Remaining P1 + important P2 issues}

### Long-term (Optimization)
{P3 + nice-to-have P2 issues}

---

## 11. Risk Assessment (optional — include when component has production risks)

{For complex components (tMap, tXMLMap, tAggregateRow, etc.) or components with known edge cases.}

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| {Risk description} | High/Medium/Low | High/Medium/Low | {How to mitigate} |

### High-Risk Job Patterns
{Job configurations that are likely to hit issues}

### Safe Usage Patterns
{Job configurations that work reliably}

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | {URL} | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | {URL} | Component definition XML |
| Real .item file examples | {URL} | Framework params, TABLE structures |
| Engine source | {path} | Feature parity analysis |
| Converter source | {path} | Converter audit |

## Appendix B: Cross-Cutting Issues

{Reference shared issues by canonical ID. Include file:line for current location.}

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |

## Appendix C: Historical Notes (optional)

{Major changes, migration notes, converter pipeline changes.}

{For complex components, add additional appendices as needed:}
## Appendix D-N: {Component-specific deep reference material}
{e.g., execution flow walkthrough, type mapping details, fix guides}

---

*Report generated: {date}*
*Last updated: {date} after {trigger}*
```

---

## Rules

1. **Every section 1-10 is mandatory.** Use "None" or "N/A" if empty — never omit sections.
2. **Section 11 is optional** — include for complex or risky components.
3. **Appendix A-B are mandatory.** Appendix C+ are optional.
4. **Issue IDs follow pattern:** `{CATEGORY}-{COMPONENT_ABBREV}-{NUMBER}` (e.g., `CONV-FID-001`, `ENG-MAP-003`)
5. **Resolved issues use strikethrough:** `~~P1~~ **FIXED**` — never removed from report.
6. **Section 3 is the source of truth** — researched from .item files (primary), _java.xml, and official docs.
7. **Section 9 counts must match** the individual sections. If Section 6 has 3 bugs and Section 5 has 2 engine issues, Section 9 totals must reflect exactly that.
8. **Section 10 recommendations derive from issue priorities** — P0s go in Immediate, P1s in Short-term, P3s in Long-term.
9. **Appendix A must cite ALL sources** used during research — URLs, file paths, .item examples.
10. **Edge-case checklist** (from METHODOLOGY.md) must be checked during every audit — results reflected in Sections 5-7.
11. **V1 only** — reports must contain zero references to v2, V2, PyETL, v1-to-v2, talend-to-v2, or v2 test files.
