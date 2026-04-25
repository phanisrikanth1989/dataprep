---
status: triaged
date: 2026-04-25
scope: manager-commits (52dbada..f0f6351)
api_findings_skipped: true
total_classified: 70 findings + 15 gaps
phase_7_1_scope: 48 items
deferred: 22 items
wont_do: 15 items
---

# Triage Matrix — Manager Commit Audit

API findings (27) skipped per user direction. This matrix covers the remaining **70 findings** from REVIEW.md, REVIEW-engine.md, REVIEW-javabridge.md, plus **15 gaps** (G-01..G-15) from `docs/v1/BaseComponent-Info.md`.

Classification rules:
- **FIX in 7.1** — load-bearing BaseComponent bug, manager-introduced regression in already-shipped phase, or build blocker
- **DEFER** — belongs to a different phase per scope-boundary rule, or is pre-existing/perf-only
- **WON'T DO** — speculative, cosmetic, or architectural disagreement with no concrete need

---

## Phase 7.1 IN-SCOPE (48 items)

### A. BaseComponent core (15 items)

| ID | File:line | Issue | Why 7.1 |
|----|-----------|-------|---------|
| CR-01 | base_component.py:683-696 | validate_schema crashes reject flow on non-nullable null | Load-bearing; affects every reject path |
| CR-02 | base_component.py:780 | Decimal precision crashes on string from JSON | Load-bearing crash |
| WR-01 | base_component.py | Wrong default for datetime missing columns (uses pd.NA / "" instead of NaT) | BaseComponent core |
| WR-02 | base_component.py | Scalar assignment for missing cols breaks dtype on empty DF | BaseComponent core |
| WR-03 | base_component.py | Empty-reject early-exit skips missing-column fill | BaseComponent core |
| G-01 | base_component.py | Datetime defaults — should use NaT/sentinel | Same as WR-01 |
| G-02 | base_component.py | Decimal columns w/o precision stay as strings forever | BaseComponent core correctness |
| G-03 | base_component.py | Float/double precision not rounded to schema precision | BaseComponent Talend-parity |
| G-04 | base_component.py | date_pattern not honored for parsing/output | BaseComponent core, ties to ENG-CR-06 |
| G-05 | base_component.py | die_on_error not checked in schema validation | BaseComponent contract |
| G-10 | base_component.py | Streaming defeats schema validation (full DF in memory) | BaseComponent perf bug |
| G-12 | base_component.py | Empty string vs null not distinguished | BaseComponent semantic |
| G-13 | base_component.py | Reject-schema validation regression (= CR-01) | Same item |
| G-14 | base_component.py | Precision-type crash (= CR-02) | Same item |

(WR-01/02/03 + G-01/04 are facets of the same area; combined design fix.)

### B. Build & infrastructure (1 item)

| ID | File:line | Issue | Why 7.1 |
|----|-----------|-------|---------|
| CR-04 | pom.xml:57-62 | Windows-absolute Maven repo path blocks Mac/Linux build | Blocks dev team; routines JAR cannot compile |

### C. file_output_delimited.py (7 items)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| CR-06 | Multi-char field_sep produces unreadable output | Phase 4 regression by manager |
| CR-09 / ENG-CR-06 | validate_schema mutates input → silent truncation downstream | Silent data loss |
| ENG-WR-04 | _apply_date_patterns writes string into datetime cols | Ties to CR-09 |
| ENG-WR-05 | escapechar="\\" silently corrupts backslash-bearing fields in non-CSV branch | Silent data loss |
| ENG-WR-11 | Config bool check fails when JSON sends `"true"` string | Common JSON pitfall |
| ENG-IN-04 | _handle_empty_input writes header using field_sep even in CSV mode | Phase 4 file format correctness |

### D. file_input_delimited.py (3 items)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| CR-03 | DataValidationError leaks through (ValueError, TypeError) catch | Phase 4 regression |
| WR-04 | _fast_path_convert reject rows have inconsistent index/columns | Phase 4 reject correctness |
| WR-06 | None output_schema → no type coercion | Phase 4 correctness |

### E. filter_rows.py (engine + converter, 7 items)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| WR-07 / ENG-IN-03 | _compare numeric/string fallback dead branch | Re-confirmed in second review |
| WR-08 | self.inputs[0] AttributeError unguarded | Crash path |
| ENG-CR-05 | Manual validate_schema short-circuits BaseComponent lifecycle | Lifecycle integrity |
| ENG-CR-07 | _resolve_java_expressions mutates self.config mid-execute | Lifecycle integrity (config_immutability) |
| ENG-WR-06 | errorMessage column may collide with user-defined column | Phase 7 regression |
| ENG-WR-07 | {{java}} strip uses fixed index 8 → mangles other markers | Reject message correctness |
| ENG-WR-08 | converter needs_review claims "engine uses eval()" — FALSE | Misleading documentation |

### F. aggregate_row.py (4 items)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| CR-05 | list_object returns joined string; union doesn't dedupe | Phase 6 Talend parity violations |
| WR-09 | median with use_financial_precision falls back to float | Phase 6 Talend parity |
| WR-10 | count ignores `ignore_null=False` | Phase 6 Talend parity |
| WR-11 | sort=True alphabetizes; Talend preserves input order | Phase 6 Talend parity |

### G. normalize.py (NEW component, 7 items)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| ENG-CR-01 | _validate_config returns list instead of raising ConfigurationError | Wrong ABC contract |
| ENG-CR-02 | iterrows()+row.copy() — O(n*m), erases dtypes | Correctness + perf |
| ENG-CR-03 | discard_trailing_empty_str discards ALL empties | Talend parity violation |
| ENG-WR-01 | pd.isna returns array for some inputs, breaks if-check | Crash path |
| ENG-WR-02 | Empty result emits stray empty-string row | Talend parity |
| ENG-WR-03 | dedupe order wrong vs trim/empty filter | Talend parity |
| ENG-WR-10 | Wrong type annotation Union[str, float, None] for cell_value | Type safety |

### H. Converter orchestrator (1 item)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| ENG-CR-04 | _propagate_input_schemas case mismatch — feature silently dead | Affects multi-input components (tMap) |

### I. Java routines (5 items, all Talend parity)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| CR-07 | Numeric.INT NumberFormatException on "100.5" — Talend accepts | Talend parity |
| CR-08 | TalendDate ParseException → bare RuntimeException kills batches | Talend parity + crash |
| WR-14 | StringHandling.LEN returns -1 for null; Talend returns 0 | Talend parity |
| WR-15 | StringHandling.INSTR bounds check uses defaultStart, not user start | Crash path |
| IN-01 | Mathematical.CHAR uses Character.forDigit — wrong for ASCII | Talend parity |

### J. Tests (1 item)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| WR-17 | test_empty_input_header_uses_input_schema references config component never reads | Test will fail when run |

### K. Cleanup that touches 7.1 files (3 items, opportunistic)

| ID | Issue | Why 7.1 |
|----|-------|---------|
| WR-16 | Numeric uses deprecated `new Float(double)` | While we're in Java routines anyway |
| ENG-IN-06 | filter_rows imports numpy inside method | While we're in filter_rows anyway |
| ENG-WR-09 | Converter outputs lookup undocumented case-sensitivity | While we're in converter anyway |

---

## DEFER (22 items)

### To Phase 8 — Code Components (3 items)

| ID | Issue | Reason |
|----|-------|--------|
| JB-WR-01 | executeJavaRow ordering fix needs same LinkedHashMap treatment | tJavaRow lives in Phase 8 |
| G-11 | NB_LINE per-input for multi-input components | tMap multi-input semantics; Phase 8 covers code components, multi-input revisit fits there |
| WR-13 | context_load type column empty-string handling | Phase 9 just shipped; light enough to fold into Phase 8 if it touches context, else leave |

### To Phase 10 — Iterate Support (1 item)

| ID | Issue | Reason |
|----|-------|--------|
| G-15 | _stats_set_by_component not reset across iterate loops | Iterate is Phase 10's owning concern |

### To Phase 12 — Integration Testing & Performance (5 items)

| ID | Issue | Reason |
|----|-------|--------|
| G-06 | No input schema validation | Boundary validation belongs to integration testing |
| WR-05 | file_input remove_empty_row double-walks | Pure perf, no correctness impact |
| WR-12 | context_load .iloc per-lookup O(n) | Phase 9 perf, not correctness |
| IN-08 | StringHandling.LTRIM O(n²) inner walk | Routines perf |
| IN-11 | _emit_message re-reads DISABLE_* flags | Micro perf |

### Pre-existing JavaBridge (3 items, not manager regressions)

| ID | Issue | Reason |
|----|-------|--------|
| JB-WR-02 | Mutable bridge state not thread-safe | Pre-existing; needs its own design phase |
| JB-WR-03 | TimeStampNano truncates sub-millisecond | Pre-existing; Phase 5.1 type-fidelity could re-open |
| JB-IN-02 | No eviction for compiledScriptClasses | Pre-existing perf |

### Other DEFER (10 items)

| ID | Issue | Reason |
|----|-------|--------|
| IN-04 | TalendDataGenerator uses java.util.Random | Already noted as awareness, not a bug |
| IN-05 | TalendString.getAsciiRandomString new SecureRandom per call | Perf only |
| IN-07 | StringHandling.TRIM only ASCII whitespace | Talend parity, low impact, defer |
| IN-09 | aggregate _decimal_std loses precision | Phase 6 Talend parity follow-up |
| JB-IN-01 | Routine namespace map rebuilds per binding | Perf |
| JB-IN-03 | executeOneTimeExpression allocates fresh GroovyShell | Perf |
| JB-IN-04 | Commit message typo | Cosmetic |
| JB-IN-05 | 4 GB allocator cap magic number | Cosmetic |
| ENG-IN-05 | Converter ignores `output_schema` / `outputs_schema` | Defer; clarify after Phase 8 schema decisions |
| ENG-IN-07 | _write_split allocates per chunk | Perf |

---

## WON'T DO (15 items)

### G-01..G-12 architectural disagreements (3 items)

| ID | Issue | Reason |
|----|-------|--------|
| G-07 | No schema default values | Talend supports `default` attribute, but not core; defer indefinitely until a job actually needs it |
| G-08 | No key attribute enforcement | Talend doesn't enforce keys at engine level either; speculative |
| G-09 | No error flow routing | Architecture-scale change; not BaseComponent's concern. Add only if a real job demands it. |

### Cosmetic / housekeeping (12 items)

| ID | Issue | Reason |
|----|-------|--------|
| IN-02 | Mathematical.main leftover test code | Harmless |
| IN-03 | TalendDate.test_* leftover | Harmless |
| IN-06 | TalendString.initMap raw Vector | Ancient pattern but works |
| IN-10 | filter_rows _compare CONTAINS string fallback | Cosmetic |
| IN-12 | Missing docstring examples | Cosmetic |
| ENG-IN-01 | normalize docstring `dedupe` default note | Cosmetic, accurate |
| ENG-IN-02 | normalize `seen: set` annotation lacks parameter | Cosmetic |

(Plus 5 IN-* items rolled into the cleanup K group above already.)

---

## Phase 7.1 Sub-area summary (for plan structure)

| Sub-area | Items | Suggested plan |
|---------|-------|----------------|
| A. BaseComponent core | 15 | 7.1-01: BaseComponent rewrite — schema validation, ordering, defaults, date/Decimal/float precision, die_on_error, streaming, empty-string-vs-null |
| B. Build (pom.xml) | 1 | 7.1-02: Maven repo path fix + verify Mac/Linux build |
| C. file_output_delimited | 7 | 7.1-03: file_output_delimited fixes (multi-char delimiter, validate_schema mutation, escape, date_patterns, JSON bool) |
| D. file_input_delimited | 3 | 7.1-04: file_input_delimited fixes (DataValidationError leak, fast_path reject, type coercion) |
| E. filter_rows | 7 | 7.1-05: filter_rows fixes (engine + converter — lifecycle violations, dead branches, errorMessage handling) |
| F. aggregate_row | 4 | 7.1-06: aggregate_row Talend parity (list_object, median precision, count/ignore_null, sort order) |
| G. normalize.py | 7 | 7.1-07: normalize rewrite (vectorized, contract-correct, Talend parity for discard/dedupe/trim) |
| H. Converter | 1 | Fold into 7.1-05 (filter_rows converter) or 7.1-08 standalone |
| I. Java routines | 5 | 7.1-08: Java routines Talend parity + bounds (Numeric.INT, TalendDate ParseException, StringHandling LEN/INSTR, Mathematical.CHAR) |
| J. Tests | 1 | Folded into 7.1-03 (test fix lives with file_output) |
| K. Opportunistic cleanup | 3 | Folded into adjacent plans |

**Total: ~8 plans across ~48 fix items.**

## Open question for discuss-phase

Should Phase 7.1 split into 7.1 + 7.2?

**Option A — Single phase 7.1** (8 plans, ~48 fixes):
- Cohesive: all are manager-commit audit fixes + BaseComponent gaps
- One phase = one rollback point, simpler state tracking
- Big phase but plans are independent (mostly per-file)

**Option B — Split 7.1 / 7.2:**
- **7.1** Foundation: BaseComponent core + Build (16 items, 2 plans). Must complete before 7.2.
- **7.2** Component regression fixes: file_input/output, filter_rows, aggregate_row, normalize, Java routines (32 items, 6 plans).
- Cleaner critical path, but adds milestone overhead.

Recommendation: Option A. The rationale for splitting (foundation-first) is satisfied by plan ordering within a single phase. 7.1-01 (BaseComponent) lands first; downstream plans rebase on it. This matches the Phase 1 pattern that did the same for engine infrastructure.
