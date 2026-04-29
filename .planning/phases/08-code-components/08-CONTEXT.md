# Phase 8: Code Components - Context

**Gathered:** 2026-04-29 (auto mode -- Claude picked recommended defaults)
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver four code-execution components with full Talend semantic parity:

- **tJava** (`java_component`) -- one-shot Java code block (job-level)
- **tJavaRow** (`java_row_component`) -- per-row Java code with REJECT flow
- **python_component** (`python_component`) -- one-shot Python block
- **python_row_component** (`python_row_component`) -- per-row Python with REJECT flow

Each must execute user-supplied code with correct Talend semantics, support `imports`, expose `context` and `globalMap` (bidirectional sync), route per-row errors via REJECT for the *Row variants, and execute Python in a secure namespace. Standardization to the Phase 7.1 BaseComponent contract + Rule 11/Rule 12 authoring rules is mandatory.

**Out of scope:** New code-language support (R, Groovy at component level), code-component DSL, sandboxed JVM (sandboxing is at the bridge level, not the component level), tContextLoad/routines (Phase 9, already complete).

</domain>

<decisions>
## Implementation Decisions

### Approach to existing partial implementations
- **D-01:** Treat the four existing files in `src/v1/engine/components/transform/` (`java_component.py` 109L, `java_row_component.py` 99L, `python_component.py` 133L, `python_row_component.py` 200L) as legacy partial implementations. Rule 1 applies: rewrite cleanly to the BaseComponent template + Rule 11/12 authoring contract. Do not patch in place.
- **D-02:** Use the rewritten `file_output_delimited.py` (Phase 7.1 third-strike rewrite, post quick task 260429-hc2) and `tFilterRow` (Phase 7.1) as the canonical reference shapes for the rewrite.

### Component structure (JAVA-03, JROW-04, PYCO-01, PYRO-01 -- standardization)
- **D-03:** Each of the four components is its own file in `src/v1/engine/components/transform/`. No supercomponent abstraction beyond a shared mixin (see D-09).
- **D-04:** `_validate_config` may only check key presence and container shape (Rule 12 from Phase 7.2). All content checks (regex, type coercion, namespace whitelist enforcement) belong in `_process` after Step 3 resolution.
- **D-05:** `_process` returns a dict with `main` (DataFrame for *Row variants, None for one-shot variants) and `reject` (DataFrame with errorMessage / errorCode columns for *Row variants). Stats updated via the existing BaseComponent `_update_stats_from_result` hook.
- **D-06:** `execute()` lifecycle is inherited unchanged. Components MUST NOT override Step 1-7c. They override only `_validate_config` and `_process`.

### Imports support (JAVA-01, JROW-01)
- **D-07:** `imports` config key holds a Java import block as raw text. At `_process` time, if `imports` is non-empty, prepend it to `java_code` with a newline separator before sending to the Java bridge. No parsing, no validation -- bridge handles compile errors.
- **D-08:** The same prepend pattern applies to tJava (job-level) and tJavaRow (per-row). For tJavaRow, the prepended-imports `java_code` is compiled ONCE at first row, reused across the loop (per Rule 11 + Phase 5.1 compiled-script pattern; Java side already supports this).

### Shared utilities (PYCO-03 -- consolidation)
- **D-09:** Create `src/v1/engine/components/transform/_code_component_mixin.py` containing `CodeComponentMixin` with the consolidated `_get_context_dict()` method (and any other shared helper that surfaces during planning). All four components inherit from this mixin AND from `BaseComponent` (Python multiple inheritance, mixin first). Do NOT add `_get_context_dict` to `BaseComponent` -- only code components need it; keeping it in a mixin tightens scope.
- **D-10:** `_get_context_dict()` returns a dict view of `self.context_manager` keyed by variable name, suitable for assignment as `context` in the user's exec namespace. Same shape used today; just deduplicated.

### Secure Python execution namespace (PYCO-02)
- **D-11:** Build the exec namespace explicitly. Allow: `pandas` (as `pd`), `numpy` (as `np`), `datetime`, `json`, `re`, `math`, `decimal.Decimal`, plus a `context` dict (see D-10), `globalMap` proxy, and `input_row` / `output_row` (for the per-row variant). Disallow `os`, `sys`, `subprocess`, `__import__`, `open`, `exec`, `eval`, `compile`, `__builtins__` (provide a tightly-scoped `__builtins__` dict with only safe builtins).
- **D-12:** Document this as a breaking change relative to the legacy partial implementation: any existing user code that imports `os` / `sys` will fail. Include a clear ConfigurationError-style message at exec time pointing to the safe alternatives (`pandas.read_csv` for file I/O, `datetime.datetime.now()` for time, etc.). No silent compatibility shim -- per project memory (`feedback_fix_source_no_fallbacks`).
- **D-13:** Whitelist enforcement happens in `_process` (after context resolution), not `_validate_config` -- the namespace itself is constructed at exec time, not config-validated.

### Per-row REJECT flow (JROW-02, PYRO-03)
- **D-14:** Per-row error in tJavaRow / python_row_component routes the offending input row to the `reject` output DataFrame with two appended columns: `errorMessage` (str, the exception message) and `errorCode` (int, default 1). Matches Talend's tJavaRow contract and the engine's existing tFilterRow REJECT flow established in Phase 7.1.
- **D-15:** The job continues processing remaining rows unless `die_on_error=True` (existing BaseComponent flag). When `die_on_error=True`, raise `ComponentExecutionError` on first per-row failure with the offending row's index and the original exception.
- **D-16:** Reject column names exactly: `errorMessage`, `errorCode` (camelCase, matching Talend conventions surfaced by tFilterRow Phase 7.1 work). Do not use `error_message` or `error`.

### Compiled Python execution (PYRO-02 -- performance)
- **D-17:** `python_row_component` compiles the user's Python source once via `compile(source, filename='<python_row_component:{component_id}>', mode='exec')` during the first row of execution (or in a one-shot pre-loop step inside `_process`). Reuse the compiled code object for every row via `exec(compiled_code, exec_namespace)`.
- **D-18:** The exec namespace is REBUILT per row (cheap dict construction) so `input_row` / `output_row` reflect the current row, but the COMPILED CODE OBJECT is shared (heavy parser work amortized once). Matches Talend's javac-once pattern at the Java side.

### Java bridge integration (JAVA-02, JROW-03 -- bidirectional sync)
- **D-19:** All Java code execution goes through the existing `JavaBridge` subprocess (Phase 2 + Phase 5.1 verified). No protocol changes. Use the established `compile_script` + `execute_script` pair from `JavaBridgeManager`.
- **D-20:** Bidirectional context/globalMap sync occurs at every bridge call site -- the existing `_sync_to_java` / `_sync_from_java` mechanism in `JavaBridgeManager` (per ENG-04 / Phase 2). Do not duplicate sync logic in the components.
- **D-21:** Per memory `feedback_test_real_bridge`: the test suite for tJava / tJavaRow MUST include `@pytest.mark.java` integration tests against a running bridge JAR (not just mocks). Mock-only tests gave false confidence in the Phase 5.1 audit.

### Test coverage (TEST-07)
- **D-22:** Each of the 4 components gets a dedicated test file in `tests/v1/engine/components/transform/` named `test_{component}.py`. Use the Phase 7.2 test-fixture pattern: manually populate `comp.config = dict(config)` before calling `_validate_config` / `_process` directly (because `BaseComponent.__init__` only sets `_original_config`).
- **D-23:** Three-test pattern per component (from Phase 7.2 LEARNINGS): (a) `_validate_config` accepts `${context.X}` literals, (b) `_process` resolves end-to-end correctly, (c) `_process` raises original exception type with original message on invalid resolved values.
- **D-24:** Java component test files include `@pytest.mark.java` integration tests requiring a running bridge JAR. Document the marker / fixture pattern in test docstrings so future contributors don't run mock-only.

### Configuration / context-var resolution
- **D-25:** Code components inherit the three-phase resolution (`{{java}}` markers + `${context.X}` + bare `context.X`) from `BaseComponent.execute()`. Components do NOT add their own resolution layer. By the time `_process` runs, all config strings are fully resolved.
- **D-26:** `java_code` and `python_code` may themselves contain `${context.X}` references that resolve to substring values for runtime substitution into the user's source. This is just normal string-config resolution -- the user's CODE is a string config field like any other. Document this clearly.

### Error type contract (consistent with Phase 7.2 Rule 12 work)
- **D-27:** `_process` raises `ConfigurationError` for resolved-value validation failures (e.g., `imports` is not a string, `python_code` is empty, namespace whitelist violation at parse time). Place these checks BEFORE any broad try/except in `_process` -- per Phase 7.2 send_mail lesson, otherwise `ConfigurationError` gets re-wrapped as `ComponentExecutionError`.
- **D-28:** Per-row exec failures inside the user's code raise `ComponentExecutionError` (with original exception as `cause`) ONLY when `die_on_error=True`. Otherwise the row is rejected (D-14).

### Claude's Discretion
- Exact mixin method names beyond `_get_context_dict` (other helpers will surface during execution; name and place sensibly)
- Per-row error log message format (use existing `[{component_id}]` prefix pattern, ASCII-only per project memory)
- Internal method ordering inside each rewritten file (follow the section-separator convention from `file_output_delimited.py`)
- Test data shapes for the 4 component test files (stay consistent with existing Phase 7.2 test files)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Authoring contract (mandatory pre-read for any planner/executor)
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` -- 12 Rules of BaseComponent subclassing. Rule 11 (Phase 7.1 contract -- standardization across components) and Rule 12 (Phase 7.2 contract -- `_validate_config` may only check key presence and container shape) are both binding for this phase.

### Engine baseline contracts
- `src/v1/engine/base_component.py` lines 204-260 -- `BaseComponent.execute()` template-method lifecycle. Steps 2 (`_validate_config`), 3 (`_resolve_expressions`), 7b (`_enforce_schema_column_order`), 7c (`_apply_output_schema_validation`).
- `src/v1/engine/components/file/file_output_delimited.py` -- canonical shape post Phase 7.1 third-strike rewrite + quick task 260429-hc2 multi-char delimiter Talend parity. Use as the structural reference.
- `src/v1/engine/components/transform/filter_rows.py` -- canonical shape for REJECT-flow components post Phase 7.1.

### Java bridge protocol
- `src/v1/java_bridge/bridge.py` -- Python-side JavaBridge client; supports `compile_script` + `execute_script`.
- `src/v1/engine/java_bridge_manager.py` -- bridge lifecycle, bidirectional sync (`_sync_to_java` / `_sync_from_java`).
- `.planning/phases/05.1-java-bridge-tmap-fix/` SUMMARY -- post-fix Arrow type conversion + compiled tMap script execution. Phase 8 must NOT reintroduce the regressions Phase 5.1 fixed.

### Prior phase summaries (for pattern reuse and lessons-carried-forward)
- `.planning/phases/07.1-manager-audit-and-basecomponent-fixes/07.1-03-SUMMARY.md` (with the 2026-04-29 addendum) -- BaseComponent template-method lifecycle, CR-06 supersession.
- `.planning/phases/07.2-validate-config-bug-sweep-move-pre-resolution-content-checks/07.2-CONTEXT.md` -- Rule 12 codification, deferred-check pattern.
- `.planning/phases/07.2-validate-config-bug-sweep-move-pre-resolution-content-checks/07.2-LEARNINGS.md` -- 5 patterns established by Phase 7.2 (deferred-check, KEEP rationale, test fixture, three-test, pinned-baseline gate). Phase 8 should reuse all five.
- `.planning/quick/260429-hc2-cleanup-of-manager-commits-43762c8-c9be1/260429-hc2-SUMMARY.md` -- Talaxie source-of-truth review pattern.

### Project-level
- `CLAUDE.md` -- ASCII-only logging, fix-source-no-fallbacks, prefer rewrite over patch, feature parity with Talend non-negotiable.
- `.planning/PROJECT.md` -- core value, constraints.
- `.planning/REQUIREMENTS.md` -- JAVA-01..03, JROW-01..04, PYCO-01..03, PYRO-01..03, TEST-07, PERF-02 acceptance criteria.

### Talend reference (parity verification)
- Talaxie source for Talend's tJava / tJavaRow / tPythonRow templates: `https://github.com/Talaxie/tdi-studio-se/tree/master/main/plugins/org.talend.designer.components.localprovider/components` -- read the `_main.javajet` for each component to verify generated-Java semantics if any ambiguity surfaces during planning.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **JavaBridge subprocess + JavaBridgeManager** -- already-stable Java execution channel (Phase 2 + Phase 5.1 hardened). Code components are CONSUMERS, not modifiers, of this infrastructure.
- **`BaseComponent.execute()` template-method lifecycle** (lines 204-260) -- Steps 1 (deepcopy original config), 2 (`_validate_config`), 3 (`_resolve_expressions`), 7b/7c (schema enforcement). Inherit unchanged.
- **`tFilterRow` REJECT flow** -- the established `errorMessage` / `errorCode` column convention from Phase 7.1; reuse exact column names and append shape.
- **Phase 7.2 test-fixture pattern** -- `comp.config = dict(config)` before direct `_validate_config` / `_process` calls. Documented in 7 Phase 7.2 test files.
- **`file_output_delimited.py` post-rewrite shape** -- section separators, docstring conventions, `_bool` helper pattern, `_validate_config` minimalism. Use as the rewrite template.

### Established Patterns
- **Three-phase config resolution** (Java markers, `${context.X}`, bare `context.X`) handled centrally by `BaseComponent.execute()` Step 3 -- code components consume resolved config, do not resolve.
- **Stats lifecycle** (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) propagated automatically by `_update_stats_from_result`. *Row variants must populate `result["reject"]` for NB_LINE_REJECT to be accurate.
- **`die_on_error` flag** lives on BaseComponent and is consulted by every component for fatal-vs-routed error handling.
- **`@pytest.mark.java` integration test marker** established in Phase 5.1 -- code-bridge tests must use it.
- **Component type alias registration** in `engine.py` `COMPONENT_REGISTRY` -- both camelCase and Talend (`tJava` / `tJavaRow`) names map to the same engine class.

### Integration Points
- **Component registry** (`src/v1/engine/engine.py:COMPONENT_REGISTRY`) -- new/renamed components must be wired here.
- **JavaBridgeManager** -- imports support (D-08) flows through `compile_script` (one-shot) and the per-row `execute_script` calls.
- **ContextManager** -- code components consume `context.var` references via the `_get_context_dict` mixin (D-09).
- **GlobalMap** -- bidirectional sync via JavaBridgeManager (Java side) and direct mutation (Python side); the `globalMap` proxy in the exec namespace surfaces both reads and writes.
- **Converter side** (`src/converters/talend_to_v1/components/code/`) -- already produces JSON configs with `java_code` / `python_code` / `imports` keys per the existing partial engine implementation. Verify converter is unchanged or document any minor adjustments. Pure engine-layer phase otherwise.

</code_context>

<specifics>
## Specific Ideas

- Pattern for the rewrite: each new file mirrors the section-separator-and-docstring shape of `src/v1/engine/components/file/file_output_delimited.py` -- this is now the canonical reference shape post-7.1 rewrite + 260429-hc2 cleanup.
- The mixin file (`_code_component_mixin.py`) follows the `_` prefix convention used elsewhere in the codebase for non-component helpers in component packages.
- Test files mirror the structure of `tests/v1/engine/components/transform/test_filter_rows.py` -- TestValidation, TestProcessing, TestRejectFlow, TestRegistration class layout.

</specifics>

<deferred>
## Deferred Ideas

- **R / Groovy / arbitrary-language code components** -- not in Talend's component family for the target jobs; would be its own phase if ever needed.
- **In-process JVM (replacing subprocess JavaBridge)** -- significant architectural change, separate phase if performance demands it. Current Py4J + Arrow is a Phase 2 / 5.1 lock.
- **Sandboxing the Java side** -- Talend itself does not sandbox; raising this would be a divergence from parity. Defer indefinitely unless legal/compliance flags it.
- **DSL or templating on top of code components** -- would be its own phase. Phase 8 ships the raw user-code execution semantics only.
- **Performance optimization beyond compiled-once-exec-per-row (D-17/D-18)** -- e.g., batch JIT, AST caching, multiprocess. PERF-02 is satisfied by D-17/D-18; deeper optimization is its own phase if measurements demand it.

</deferred>

---

*Phase: 08-code-components*
*Context gathered: 2026-04-29 (auto mode)*
