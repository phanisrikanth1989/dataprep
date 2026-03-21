# V1 Engine Audit — Methodology & Scoring Framework

## Purpose

This audit measures every v1 component against its Talend equivalent across multiple dimensions to produce an actionable report for developers migrating 1000+ Talend jobs to the v1 Python engine.

## Audience

Developers experienced with Talend who have Python skills and are using AI assistance to implement fixes.

## Scope

- All ~50 implemented v1 engine components
- The `complex_converter` (Talend XML to v1 JSON)
- Converter + engine coverage in a single per-component report
- Database components (Oracle, MSSQL) are **excluded**
- **V1 only** — reports must contain zero references to v2, V2, PyETL, v1-to-v2 converters, talend-to-v2 converters, or any v2 test files

---

## Priority Definitions

| Priority | Label | Definition | Action Required |
|----------|-------|------------|-----------------|
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

Source: Talend documentation, Talend Studio reference, online resources.

### 2. Converter Coverage (XML → v1 JSON)

Does `complex_converter/component_parser.py` correctly extract all Talend XML data for this component?

| Check | Description |
|-------|-------------|
| **Parameter extraction** | Every `elementParameter` Talend emits is captured |
| **Parameter mapping** | Raw XML names correctly mapped to v1 config keys |
| **Schema extraction** | All `metadata/column` attributes captured (name, type, nullable, length, precision, pattern) |
| **Expression handling** | Java expressions detected and marked with `{{java}}` |
| **Context variable wrapping** | `context.var` references wrapped as `${context.var}` |
| **Table parameters** | Nested `elementValue` groups parsed correctly (grouping, ordering) |
| **Connection types** | All FLOW/REJECT/FILTER/ITERATE connectors mapped |
| **Quote/entity handling** | `&quot;`, `&#xD;&#xA;`, hex values decoded properly |
| **Missing parser method** | Does the dispatch in converter.py have a valid target? |

### 3. Engine Feature Parity

Does the Python component produce the same results as the Talend component?

| Check | Description |
|-------|-------------|
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

### 4. Code Quality

| Check | Description |
|-------|-------------|
| **Bugs** | Confirmed runtime errors, logic errors, typos |
| **Naming consistency** | Config keys, class names, parameter names follow conventions |
| **STANDARDS.md compliance** | Follows `docs/v1/STANDARDS.md` |
| **Error handling** | Proper exception types, consistent die_on_error, no bare except |
| **Dead code** | Unused methods, unreachable branches |
| **Debug artifacts** | `print()` statements, hardcoded paths, TODO comments |
| **Security** | Unsandboxed eval(), injection risks |
| **Docstrings/comments** | Adequate inline documentation |
| **Method contract** | `_validate_config()` returns `List[str]`, `_process()` returns `Dict[str, Any]` |

### 5. Performance & Memory

| Check | Description |
|-------|-------------|
| **Memory efficiency** | Unnecessary copies, full loads vs streaming |
| **Streaming support** | Works in HYBRID mode without data loss |
| **Scalability** | O(n) vs O(n^2) patterns, large file handling |
| **Type handling** | BigDecimal precision, nullable int, date parsing |
| **DataFrame operations** | Uses vectorized pandas vs row-by-row iterrows() |

### 6. Testing Coverage

| Check | Description |
|-------|-------------|
| **Unit tests exist** | Any test file for this component? |
| **Happy path tested** | Basic functionality verified |
| **Edge cases tested** | Empty input, null values, missing files, encoding |
| **Error paths tested** | die_on_error=True/False, invalid config |
| **Integration tested** | Component tested in a multi-step job |

---

## Report Structure

### Per-Component Report (`docs/v1/audit/components/<ComponentName>.md`)

Each report follows a fixed structure — see `tFileInputDelimited.md` as the gold standard template.

### Cross-Cutting Issues (`docs/v1/audit/CROSS_CUTTING_ISSUES.md`)

Issues that affect the entire engine, not a single component:
- `_update_global_map()` crash (base_component.py:304 — undefined `value` variable)
- `GlobalMap.get()` crash (global_map.py:28 — undefined `default` parameter)
- `replace_in_config` literal `[i]` bug (base_component.py:174 — Java expressions in lists never resolved)
- `validate_schema` inverted nullable logic (base_component.py:351 — nullable columns get fillna(0))
- `_execute_streaming` drops reject DataFrames (base_component.py:267-278)
- HYBRID streaming mode produces incorrectly sorted/ordered output for stateful components
- `self.config` mutated by `execute()` — non-reentrant in iterate loops
- Component status never reaches SUCCESS when globalMap is set
- `_update_global_map()` crash in error handler masks original exceptions
- Trigger evaluator: no `((Boolean)...)` regex, `!` replacement corrupts `!=`
- Engine error handling flow, die_on_error consistency, exit code propagation
- Missing component implementations (tFileList, tFlowToIterate, tRunJob, tPrejob, tPostjob)
- Converter systemic issues (broken imports from aggregate, missing parser methods)

### Summary Scorecard (`docs/v1/audit/SUMMARY_SCORECARD.md`)

Traffic-light matrix: every component x every dimension = R/Y/G with issue counts.

---

## Scoring

| Score | Meaning |
|-------|---------|
| **R (Red)** | Broken, missing, or will produce wrong results |
| **Y (Yellow)** | Partially works, gaps exist, needs attention |
| **G (Green)** | Works correctly, meets standards |
| **N/A** | Not applicable to this component |

---

## Audit Process

Each component goes through a **two-pass review process**:

### Pass 1: Initial Audit
- Research Talend documentation online for the component
- Read the v1 engine implementation (every line)
- Read the converter code (dispatch + parser + parameter mapping)
- Write the full audit report following the gold standard template

### Pass 2: Adversarial Review
- A separate reviewer reads the report AND the source code
- Mindset: "Find at least 3-5 issues the report missed"
- Focuses on edge cases, cross-class interactions, and behavioral subtleties
- Findings are incorporated back into the report before commit

### Mandatory Edge-Case Checklist

Every audit MUST check these cross-cutting concerns:

| Check | Why |
|-------|-----|
| NaN handling (`pd.isna()` vs `is None`) | pandas uses NaN, not None — `value is None` misses NaN |
| Empty strings in config keys | Can produce crashes (e.g., `str.split("")` raises ValueError) |
| Empty DataFrame input (0 rows with columns vs None) | Returning `pd.DataFrame()` loses column schema |
| HYBRID streaming mode via base class | Base class chunks and calls `_process()` per chunk — stateful components break |
| `_update_global_map()` crash effect | Crashes ALL components when globalMap is set — results lost, status stuck at RUNNING |
| Component status reaching SUCCESS | Line 220 unreachable when `_update_global_map()` crashes on line 218 |
| Thread safety for parallel subjobs | ContextManager, GlobalMap, JavaBridge are shared — no locking |
| Type demotion through iterrows/Series reconstruction | `Decimal` → `float64`, `datetime64` → `object` |
| `validate_schema` nullable logic (inverted) | `nullable=True` triggers `fillna(0)` — should be the opposite |
| `_validate_config()` called or dead code | Most components define it but never call it |

---

## Known Cross-Cutting Bugs

These bugs appear in EVERY component report (referenced by component-specific IDs):

| Bug | Location | Impact |
|-----|----------|--------|
| `_update_global_map()` undefined `value` | `base_component.py:304` | Crashes all components when globalMap is set. Results lost. |
| `GlobalMap.get()` undefined `default` | `global_map.py:28` | Crashes any direct `.get()` call. `get_component_stat()` line 58 also fails. |
| `replace_in_config` literal `[i]` | `base_component.py:174` | Java expressions in list config values never resolved back. |
| `validate_schema` inverted nullable | `base_component.py:351` | Nullable int columns get `fillna(0)` — nulls silently become 0. |
| `_execute_streaming` drops rejects | `base_component.py:267-278` | Only `result['main']` collected in streaming — reject data lost. |
| `self.config` mutation | `base_component.py:202` | `resolve_dict()` replaces config — non-reentrant in iterate loops. |
| `__repr__` mismatched parenthesis | `base_component.py:382` | Cosmetic but indicates lack of review. |
