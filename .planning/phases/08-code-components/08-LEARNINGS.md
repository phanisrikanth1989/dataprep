---
phase: 08
phase_name: "Code Components -- tJava, tJavaRow, python_component, python_row_component"
project: "DataPrep -- Talend ETL Migration Engine"
generated: "2026-04-29"
counts:
  decisions: 7
  lessons: 6
  patterns: 6
  surprises: 6
missing_artifacts:
  - "08-UAT.md"
  - "08-VERIFICATION.md (separate phase-level VERIFICATION; equivalent content in 08-PHASE-SUMMARY.md)"
---

# Phase 8 Learnings: Code Components

## Decisions

### Rewrite over patch for all 4 legacy partial implementations
The 4 existing files (`java_component.py` 109L, `java_row_component.py` 99L, `python_component.py` 133L, `python_row_component.py` 200L) were rewritten cleanly, not patched. They predated the Phase 7.1 BaseComponent template + Rule 11/Rule 12 authoring contract.

**Rationale:** Project memory rule `feedback_rewrite_over_patch` -- prefer clean rewrites for systemic issues. Patching would have left unaddressed anti-patterns (manual `_update_stats`, manual `_sync_from_java`, missing `@REGISTRY.register`, content checks in `_validate_config`, errorCode='PYTHON_ERROR' string) drifting against newer infrastructure.
**Source:** 08-CONTEXT.md D-01, D-02; 08-PATTERNS.md AP-1..AP-12; 08-PHASE-SUMMARY.md "What Shipped"

---

### Shared CodeComponentMixin (NOT in BaseComponent) -- mixin-first MRO
The consolidated `_get_context_dict()` and the namespace whitelist constants (`_SAFE_BUILTIN_NAMES`, `_SAFE_NAMESPACE_GLOBALS`, `_build_safe_builtins`) live in a new `_code_component_mixin.py`. All 4 components inherit `class X(CodeComponentMixin, BaseComponent)` (mixin first per Python multiple-inheritance MRO conventions).

**Rationale:** `BaseComponent` is the shared lifecycle for ALL components; code-execution helpers are specific to the 4 code components. Mixin tightens scope. Module-level constants live in the mixin file so Plans 02 and 04 import them rather than redefining (catches drift surface).
**Source:** 08-CONTEXT.md D-09, D-10; 08-01-SUMMARY.md; PYCO-03 closure

---

### Allow-list Python exec namespace -- documented as hygienic, not adversarial-proof
Explicit allow-list (`pandas`, `numpy`, `datetime`, `json`, `re`, `math`, `decimal.Decimal`, plus `context` dict, `globalMap` proxy, `input_row`/`output_row`). Disallow `os`, `sys`, `subprocess`, `__import__`, `open`, `exec`, `eval`, `compile`, plus a tightly-scoped `__builtins__` dict.

**Rationale:** PYCO-02 mandates secure namespace. An allow-list is more secure than a deny-list. **Honesty caveat documented in module docstring:** Python `exec` is NOT a true sandbox -- pure-Python bypass via `__subclasses__`/`__mro__` introspection is achievable. This is hygiene against accidental misuse by internal Citi job authors, not adversarial-input protection.
**Source:** 08-CONTEXT.md D-11..D-13; 08-RESEARCH.md Pitfall #3; 08-PHASE-SUMMARY.md "Limitation 1"

---

### Talend parity revision 2 -- 3 corrections after Talaxie source verification
After primary-source verification of Talaxie tdi-studio-se, three plan claims were overturned:
1. **java_row_component has NO REJECT** (Talend tJavaRow has no REJECT connector and no per-row try/catch). Errors propagate up via `_process` raise.
2. **python_row_component reject schema is errorMessage-only** -- no `errorCode` field (Talend's tFilterRow reject schema is a single `errorMessage` of `id_String` type).
3. **One-shot passthrough is a DataPrep data-flow semantic, not a Talend feature** -- Talend's tJava is code-block-only with no row iteration; passthrough is just "the component doesn't transform rows" in DataPrep's data-flow graph.

**Rationale:** User pushback was direct: "Don't have faith in audit docs alone -- they might be stale." Verified against `tJavaRow_java.xml`, `tJavaRow_main.javajet`, `tJava_begin.javajet`, `tFilterRow_java.xml`, `tMap_main.inc.javajet`. Corrections applied in place to D-14, D-16; D-29 added.
**Source:** 08-PHASE-SUMMARY.md "Talend Parity Claims Correction (revision 2)"; 08-DISCUSSION-LOG.md revision-2 Auto-Resolved section; 08-CONTEXT.md D-14 (rewritten), D-16 (rewritten), D-29 (new)

---

### CONTEXT.md D-26 superseded -- code bodies skip context resolution
`ContextManager.SKIP_RESOLUTION_KEYS` at `src/v1/engine/context_manager.py:37-41` excludes `python_code`, `java_code`, and `imports` from `${context.X}` resolution (this is ENG-18 from Phase 1). User code accesses context **programmatically** via `context['VAR']` dict (Python) or bridge sync (Java), NOT via substring substitution into source.

**Rationale:** D-26's original claim ("java_code and python_code may themselves contain ${context.X} references that resolve to substring values") was inverted from reality. Honoring `SKIP_RESOLUTION_KEYS` is the correct behavior.
**Source:** 08-PHASE-SUMMARY.md "CONTEXT.md D-26 Supersession"; 08-RESEARCH.md Pitfall #1; 08-CONTEXT.md (D-26 marked SUPERSEDED inline)

---

### JROW-02 reinterpretation -- error propagation satisfies "REJECT output flow for per-row Java errors"
REQUIREMENTS.md JROW-02 reads: "Implement REJECT output flow for per-row Java execution errors." Talend's tJavaRow has no such REJECT flow (verified Talaxie). Phase 8 reinterprets JROW-02 as "errors are properly raised and surfaced (no silent failure)" rather than as a REJECT connector. Verified by `TestErrorPropagation::test_bridge_exception_propagates`.

**Rationale:** Talend parity is non-negotiable. Implementing a REJECT flow Talend doesn't have would be a DataPrep extension, not a parity feature. v2 enhancement could add `executeJavaRowWithReject` bridge variant if business need arises.
**Source:** 08-PHASE-SUMMARY.md "Requirement Closure Table"; 08-CONTEXT.md D-14 (revision 2); 08-DISCUSSION-LOG.md Q-REJECT verdict

---

### compile-once exec-many for python_row_component (PYRO-02 / PERF-02)
`compile(source, filename='<python_row_component:{component_id}>', mode='exec')` runs ONCE at first row in `_process`. Reuse the compiled code object via `exec(compiled_code, exec_namespace)` for every subsequent row. Rebuild exec namespace per row (cheap dict construction); reuse compiled code object (heavy parser work amortized).

**Rationale:** REQUIREMENTS.md PYRO-02 mandates "compile once outside loop, exec per row". Mirrors Talend's javac-once pattern at the Java side. Verified deterministically by `TestCompileOnce::test_compile_called_once` (monkeypatches `builtins.compile`, asserts call count == 1 across 100 rows).
**Source:** 08-CONTEXT.md D-17, D-18; 08-04-SUMMARY.md TestCompileOnce; PERF-02 closure

---

## Lessons

### Audit docs can be stale -- verify against Talaxie javajet templates, not v1 docs
This session caught THREE separate audit-doc errors via direct Talaxie source review:
- `tReplace.md` audit claimed advanced mode is column-based; Talaxie `tReplace_java.xml` shows `FIELD="String"` (literal regex, not column ref). Caught earlier in the manager-commit cleanup quick task.
- Phase 7.1 CR-06 contract was over-strict; Talend silently truncates multi-char delimiters per `tFileOutputDelimited_main.javajet:645-651`. Caught earlier.
- Phase 8 planning claimed `errorCode` matches "tFilterRow Phase 7.1 conventions"; tFilterRow's reject schema in Talaxie has no errorCode -- the field was invented in Phase 7.1's rewrite and propagated as "Talend convention" in Phase 8 plan. Caught by user pushback in this phase.

**Context:** Three different audit/plan/SUMMARY documents in the v1 planning trail had each made a Talend-parity claim that primary-source verification refuted. The pattern: "we cited it" doesn't mean "we read it correctly." Always verify against Talaxie javajet/xml directly when a Talend-parity claim is load-bearing.
**Source:** 08-PHASE-SUMMARY.md "Talend Parity Claims Correction (revision 2)"; 08-DISCUSSION-LOG.md revision-2 section; user feedback throughout the planning iterations

---

### Java RowWrapper exposes get/set, not put -- Groovy MOP swallows .put silently
Real-bridge tests in `test_java_row_component.py` initially used `output_row.put("col", value)` which compiled fine but the rows hung indefinitely. Cause: Groovy's metaobject protocol (MOP) swallows arbitrary `.method(...)` calls on dynamic objects without raising `MissingMethodException` immediately; the put was a no-op while the loop iteration spun. Fix: `output_row.set("col", value)` -- the actual `RowWrapper.setOutputRow(Map)` API surface used by `JavaBridge.executeJavaRow`.

**Context:** Discovered during Plan 05 Task 1 java integration test wiring. Auto-fixed during execution; documented in `08-05-SUMMARY.md` as Rule 1 deviation.
**Source:** 08-05-SUMMARY.md "Auto-fixes applied during Task 1" (item 2); JavaBridge.java row execution path

---

### JavaBridge.global_map is the sync target, not engine.GlobalMap
Plan 05's Java integration tests initially asserted against `comp.global_map` to verify globalMap writes from Java code. Tests failed because `engine.py` does NOT wire any automatic mirror from `JavaBridge.global_map` (the dict on the bridge subprocess wrapper) back into `engine.GlobalMap` (the engine-level shared state). The actual sync target is `comp.java_bridge.global_map`.

**Context:** Plan 05 Task 1 auto-fix. Bidirectional sync exists between `ContextManager` and `JavaBridge.context`, but `GlobalMap` <-> `JavaBridge.global_map` is a per-component bridge property without automatic mirroring. If tests want to assert post-execute globalMap state from the engine side, they must inspect the bridge's dict directly OR call a future helper that flushes back. Worth noting for Phase 10+ tests.
**Source:** 08-05-SUMMARY.md "Auto-fixes applied during Task 1" (item 1)

---

### Conftest fixture path resolution: parents[N] math is brittle
The `_find_java_bridge_jar` helper in `tests/v1/engine/conftest.py` had two bugs:
1. **Fallback used parents[2]** (= `tests/`) instead of `parents[3]` (= repo root). Off-by-one in the parents-list count.
2. **Git common-dir branch** ran `Path(common_dir).resolve()` which resolved relative paths against the CURRENT process cwd, not the subprocess cwd that `git rev-parse --git-common-dir` was invoked with.

Combined effect: all 4 `@pytest.mark.java` integration tests SKIPPED silently (with a "JAR not found at tests/src/v1/java_bridge/..." reason that masked the bug as a "missing build" rather than a "wrong path computation"). Caught by the orchestrator's de-facto checkpoint verification (running the 6-step plan), not by the executor's own self-check inside the worktree.

**Context:** The executor ran tests inside its worktree where pytest's cwd happened to make the relative path resolve correctly; main-repo invocation broke it. Future test fixtures that compute repo-relative paths should explicitly assert `(some_known_file).exists()` before returning, not rely on `parents[N]` math + a silent skip.
**Source:** 08-05-SUMMARY.md "Bug found and fixed (commit `af5eb66`)"; commit `af5eb66`

---

### Phase 7.2 patterns reused successfully -- five-for-five
Every one of the five patterns codified by Phase 7.2 LEARNINGS was reused in Phase 8 without modification:
1. Deferred-check pattern (Rule 12)
2. KEEP rationale comment template
3. Test fixture pattern (`comp.config = dict(config)` for direct method calls)
4. Three-test pattern (`${context.X}` literal pass-through; end-to-end resolution; original exception type/message)
5. Pinned-baseline regression gate

**Context:** Validates that Phase 7.2's institutional knowledge transfer worked. The patterns were citable in plans (`<read_first>` blocks linked back to 07.2-LEARNINGS.md) and the executor agents applied them mechanically. Worth maintaining across future phases (10, 11, 12).
**Source:** 08-PHASE-SUMMARY.md "Phase 7.2 LEARNINGS Continuity"; cross-references in Plans 01-04

---

### Plan-checker iteration is structural defense even when CONTEXT.md is detailed
Plan-checker iteration 1 caught 4 blockers + 5 warnings on a 28-decision CONTEXT.md. Iteration 2 caught 2 more blockers (VALIDATION.md drift and JROW-02 frontmatter omission) introduced by the revision 1 fixes. Without the loop, the plan would have shipped with: silent scope expansions, dependency-graph errors, stale validation contract, missing requirement-coverage frontmatter, fragile grep gates, hedged tests.

**Context:** Detailed CONTEXT.md is necessary but not sufficient. The plan-checker is the structural defense against unconscious drift between intent and plan. Run it at every revision pass on phases that have non-trivial structure.
**Source:** Plan-checker iteration 1 + iteration 2 reports; 08-DISCUSSION-LOG.md revision-2 section

---

## Patterns

### Mixin-first MRO with module-level constants imported by consumers
For shared component-family helpers and constants:
1. Define helpers as methods on a mixin class (`CodeComponentMixin`).
2. Define constants at module level alongside the mixin.
3. Component classes use `class X(MixinClass, BaseComponent)` -- mixin FIRST so its methods take precedence in MRO.
4. Component files IMPORT constants from the mixin module rather than redefining locally.
5. Acceptance grep gate: `grep -c "^_SAFE_BUILTIN_NAMES" component_file.py` returns 0 (no local redefinition).

**When to use:** Any time 2+ components share helper logic AND constants. Avoids drift between copies (revision-1 Warning 7 in this phase). Tighter scope than putting helpers in `BaseComponent`.
**Source:** 08-CONTEXT.md D-09, D-10; 08-01-SUMMARY.md mixin design; 08-PATTERNS.md S-3 + S-7

---

### compile-once exec-many for per-row Python user code
Pattern for any per-row Python `exec` loop:
```
def _process(self, input_data):
    code_obj = compile(self.config['python_code'], f'<{self.id}:python>', 'exec')
    for idx, row in input_data.iterrows():
        ns = self._build_safe_namespace(row, ...)
        try:
            exec(code_obj, ns)
            ...
        except Exception as e:
            ...
```
Compile once at first row (or in pre-loop step); reuse compiled code object across rows; rebuild exec namespace per row (cheap dict construction).

**When to use:** Any user-supplied Python code that runs N times per execute(). Exec on string source repeatedly is parser-bound; compiled code object skips parser work. Mirrors Talend's javac-once pattern.
**Source:** 08-CONTEXT.md D-17, D-18; 08-04-SUMMARY.md TestCompileOnce; PERF-02 closure

---

### Pre-broad-try ConfigurationError raises in _process
Where a `_process` body has a broad `try: ... except Exception as e: raise ComponentExecutionError(...)` block, any new content-validation `raise ConfigurationError(...)` must be placed BEFORE that block. Otherwise the broad `except` re-wraps `ConfigurationError` as `ComponentExecutionError`, breaking type contracts for callers and tests.

**When to use:** Whenever the deferred-check pattern (Rule 12) is applied to a component that has an existing broad try/except in `_process`. Extends Phase 7.2's send_mail lesson.
**Source:** 08-CONTEXT.md D-13, D-27; 08-PHASE-SUMMARY.md "Phase 7.2 LEARNINGS Continuity"; 07.2-LEARNINGS.md surprise #4 (carried forward)

---

### @pytest.mark.java + session-scoped java_bridge fixture for real-bridge tests
For tests that must exercise the real Java bridge (per memory `feedback_test_real_bridge`):
1. Mark test with `@pytest.mark.java`.
2. Inject the session-scoped `java_bridge` fixture (defined in `tests/v1/engine/conftest.py`).
3. Skip cleanly if JAR is missing -- with an actionable build hint.
4. Verify path resolution by checking `(some_known_file).exists()` BEFORE returning the path -- never rely on `parents[N]` math + silent skip.

**When to use:** Any time a code-execution component test needs to verify real Groovy/JVM behavior (round-trip Arrow data, compile-once bridge semantics, context/globalMap sync). Mock-only tests for these surfaces have given false confidence in past phases.
**Source:** 08-05-SUMMARY.md fixture wiring; commit `af5eb66` (path resolution fix); memory `feedback_test_real_bridge`

---

### Talaxie javajet primary-source verification for Talend parity claims
Before writing or accepting a "Talend parity" claim:
1. Open the relevant `*_java.xml` for parameter definitions (FIELD type, default values, connector types, schema definitions).
2. Open the relevant `*_main.javajet` (or `_begin.javajet`) for generated-Java semantics (row loops, try/catch wrappers, error routing, column construction).
3. For comparison, open a known-canonical-with-this-feature component's javajet (e.g., tFilterRow for REJECT, tMap for error semantics).
4. Cite specific line ranges in the plan/decision rather than a generic "matches Talend".

**When to use:** Any decision that claims Talend parity. Three audit-doc errors in this session (tReplace, CR-06, errorCode) were caught only by direct Talaxie verification. The audit docs in `docs/v1/audit/components/` are useful summaries but not authoritative -- the javajet templates ARE the authority.
**Source:** Quick task 260429-hc2 (tReplace verification); Phase 7.2 LEARNINGS surprises (CR-06 verification); 08-PHASE-SUMMARY.md (Phase 8 revision-2 verification)

---

### Honest extension marking: every DataPrep extension is labeled in the module docstring
For any behavior that is NOT Talend parity (DataPrep-specific data-flow semantic, DataPrep-only REJECT extension, secure namespace whitelist, etc.), the component's module docstring must explicitly mark it as a DataPrep extension with a one-line cite of why Talend doesn't have it. Failing to mark extensions causes future contributors to assume they're parity features and over-invest in maintaining them.

**When to use:** Every component file. Examples in Phase 8: `python_row_component.py` docstring explicitly notes "errorMessage-only REJECT is a DataPrep extension; Talend tJavaRow has no native REJECT connector"; `python_component.py` docstring notes the namespace whitelist is "hygienic, not adversarial-proof"; `java_component.py` docstring notes passthrough is "DataPrep data-flow semantic" with cite to `tJava_begin.javajet`.
**Source:** 08-PHASE-SUMMARY.md "Talend Parity Claims Correction" + module docstring conventions adopted in Plans 01-04

---

## Surprises

### errorCode field doesn't exist anywhere in Talend's reject schemas
The plan was about to ship `errorCode=int(1)` on python_row_component reject rows and `errorMessage=str + errorCode=int(1)` on java_row_component batch rejects, citing "matches tFilterRow Phase 7.1 conventions." Direct Talaxie verification: `tFilterRow_java.xml` reject schema is a SINGLE column `errorMessage` (`id_String`, length 255). `tMap_main.inc.javajet` only emits `errorMessage` (String) and `errorStackTrace` (String). **No errorCode anywhere in Talend's reject schemas.**

**Impact:** errorCode was a DataPrep invention that propagated through Phase 7.1 tFilterRow rewrite into Phase 8 plan as "matches Talend." Caught and dropped at revision 2. Phase 7.1's tFilterRow may still carry the invented field -- flagged for a future audit.
**Source:** 08-PHASE-SUMMARY.md "Talend Parity Claims Correction (revision 2) Correction 1"; user pushback that triggered the verification

---

### JavaBridge.executeJavaRow had a per-row try block but rethrew -- "all-or-nothing" was framing, not a protocol limit
The plan's revision 1 framed the lack of per-row REJECT for tJavaRow as "JavaBridge.executeJavaRow is all-or-nothing per D-19 lock; future BRDG-* phase needed." Reading `JavaBridge.java:209-247` directly: the per-row try block ALREADY exists at line 210; the only thing making it all-or-nothing is the rethrow at line 246. A 5-line body change (accumulate to a reject array, return alongside outputArrays) would not alter the API signature.

**Impact:** Q2 framing was misleading. But it became moot at revision 2 because Talend itself has no REJECT for tJavaRow -- so the "v1 limitation, future BRDG-* phase" was solving a problem that doesn't exist for parity work. Net: framework freed from a phantom commitment. If a DataPrep-specific Java reject contract is ever wanted, the bridge change is small and well-bounded.
**Source:** 08-RESEARCH.md Pitfall #2; 08-PHASE-SUMMARY.md "What is NOT a limitation any more (revision 2 collapse)"

---

### Conftest fixture path bug silently skipped 4 java tests
Plan 05's executor reported "4 passed, 1 xfailed" inside its worktree, but main-repo invocation showed "4 SKIPPED, 1 xfailed". Cause: `_find_java_bridge_jar` had off-by-one parents-list math AND wrong cwd resolution for the git common-dir branch. The skip masked itself as a "missing JAR" condition rather than a "wrong path computation" -- if the orchestrator hadn't run the 6-step verification manually, the bug would have shipped silently.

**Impact:** Caught by orchestrator-level verification, not by the executor's worktree-local self-check. Pattern surfaced for future phases: when a test fixture computes a path, ALWAYS assert (some_known_file).exists() before returning, never rely on `parents[N]` arithmetic + silent skip-on-missing. Bug-fix commit `af5eb66`.
**Source:** Orchestrator's de-facto checkpoint verification (Wave 4); commit `af5eb66`

---

### `output_row.put(...)` in Groovy hung silently
Initial real-bridge integration tests used `output_row.put("col", value)` in user-supplied Java code. The `.put` calls compiled fine but the row loop spun without progress and the test eventually timed out. Cause: Groovy's metaobject protocol (MOP) on a Java `RowWrapper` instance doesn't raise `MissingMethodException` immediately for `.put` -- it eats the call. The actual API surface is `output_row.set("col", value)`.

**Impact:** Required reading the `RowWrapper` Java source to find the right API. Test fixtures rewritten. Future integration tests should reference `RowWrapper.setOutputRow(Map)` / `RowWrapper.getInputRow()` explicitly. This Groovy-MOP-eats-bad-calls pattern is a Phase 5.1 echo (similar surface area; different specific call). Worth a follow-up audit to see if the RowWrapper API can be hardened to throw on unknown method calls.
**Source:** 08-05-SUMMARY.md auto-fix #2

---

### CONTEXT.md D-26 was inverted from reality -- caught only by Pitfall analysis
Original D-26 said: "java_code and python_code may themselves contain ${context.X} references that resolve to substring values for runtime substitution into the user's source." Reality (per `ContextManager.SKIP_RESOLUTION_KEYS` at lines 37-41, ENG-18 from Phase 1): code bodies are EXPLICITLY EXCLUDED from context resolution. User code reads context programmatically via the dict, not via substring substitution.

**Impact:** D-26 would have driven a re-implementation of context resolution inside the code components -- duplicating logic that ENG-18 already prevents. Plan-time research caught it (RESEARCH.md Pitfall #1). Plans 01-04 honor `SKIP_RESOLUTION_KEYS`. D-26 marked SUPERSEDED in CONTEXT.md; PHASE-SUMMARY is the canonical correction.
**Source:** 08-RESEARCH.md Pitfall #1; 08-PHASE-SUMMARY.md "CONTEXT.md D-26 Supersession (load-bearing)"

---

### REQUIREMENTS.md JROW-02 was a Talend-impossible requirement
JROW-02 reads: "Implement REJECT output flow for per-row Java execution errors." Talaxie verification: Talend's tJavaRow has NO native REJECT -- no REJECT connector in `_java.xml`, no try/catch in `_main.javajet`, no DIE_ON_ERROR parameter. The requirement as literally written cannot be satisfied AS Talend parity.

**Impact:** Required reinterpretation at plan time: "REJECT output flow" -> "errors are properly raised and surfaced (no silent failure)." Verified at component layer by `TestErrorPropagation::test_bridge_exception_propagates`. The reinterpretation was recorded in Plan 03 frontmatter (with inline note), Plan 06 PHASE-SUMMARY closure table, and 08-DISCUSSION-LOG.md. Future requirements drafting should validate REQUIREMENTS.md text against Talaxie source, not just engine code wishes.
**Source:** 08-PHASE-SUMMARY.md "Requirement Closure Table" JROW-02 row; 08-CONTEXT.md D-14 (revision 2); JROW-02 reinterpretation in Plan 03

---
