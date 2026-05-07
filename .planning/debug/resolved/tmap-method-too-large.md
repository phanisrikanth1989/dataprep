---
status: resolved
trigger: "tMap throws MethodTooLargeException when generated Groovy run() method exceeds JVM 64KB bytecode limit at high column counts"
created: 2026-05-07T00:00:00Z
updated: 2026-05-07
---

## Current Focus

hypothesis: _build_compiled_script in src/v1/engine/components/transform/map.py emits a single monolithic Groovy script. GroovyShell.parse() compiles the entire per-row body into ONE run() method on the generated Script subclass. Bytecode = sum across all outputs * all columns + variables + filters + try/catch wrapper. With aggregate column count high enough (250+ columns across outputs), run() bytecode exceeds the JVM hard limit of 65,535 bytes per method, triggering groovyjarjarasm.asm.MethodTooLargeException.
test: Build a regression test that synthesizes a tMap config with ~250 columns (1 main + 1 lookup, mix of trivial passthrough + null-check + method-call expressions). Today: throws MethodTooLargeException. After fix: compiles + executes cleanly via the real Java bridge (per memory: feedback_test_real_bridge -- mock-only tests gave false confidence).
expecting: Refactor confirms the bytecode-budget hypothesis; the failing test goes green; existing 100+ tMap tests stay green; no Java bridge API changes; BRDG-06 compile-once / execute-many contract preserved.
next_action: Reproduce the bug with a synthetic 250-column fixture, then refactor _build_compiled_script to emit per-output helper methods (def evalOutput_<name>(...)) called from a thin run() loop. Helpers receive everything as arguments (no Groovy script-binding lookup from inside helpers). Filter folds into helper (returns null on rejection). die_on_error semantics unchanged.

## Symptoms

expected: tMap with hundreds of columns across outputs compiles and executes via the Java bridge compile-once / execute-many path. Phase 5.1 closure-dispatch fix already proved this path works for moderate column counts.
actual: Groovy compilation throws groovyjarjarasm.asm.MethodTooLargeException (often wrapped in groovy.lang.GroovyRuntimeException) when total per-row bytecode crosses 64KB. The generated Script subclass cannot be loaded by the JVM because its run() method exceeds the class-file Code attribute limit.
errors: groovyjarjarasm.asm.MethodTooLargeException: Method too large: <script>.run ()Ljava/lang/Object; thrown from JavaBridge.compileTMapScript (src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:540 GroovyShell.parse). Surfaces in Python as ComponentExecutionError with cause set to the underlying Java exception.
reproduction: Convert/synthesize a tMap job with 1 main input + 1 lookup, single output containing 250 columns where ~1/3 are trivial passthrough (main.col), ~1/3 are null-check + cast, ~1/3 are method-call chains (e.g. Numeric.parseDouble, TalendString.trim). Run through ETLEngine with java_config.enabled=true. Today: throws MethodTooLargeException at compile time. Expected after fix: compiles, executes, output DataFrame matches expectations.
started: This bug has always existed structurally (the script generator was never bounded against JVM bytecode limits), but only surfaces now that real Citi Talend jobs with 200+ column tMaps are being migrated. Discovered during user testing after the Windows iteration-hang fix landed (BRDG-06 cache-class-not-instance) -- that fix preserved performance across iterations but did not address the latent method-size limit.

## Scope (locked by user)

- Max 250 columns per output ever -- confirmed by user.
- DO NOT add variable-block splitting, recursive column-chunking, or "expression too big" error path. Out of scope.
- Only fix needed: per-output method split.

## Fix shape (pre-agreed with user)

Generated Groovy after fix:

```
def evalOutput_<name>(int i, RowWrapper main_row, RowWrapper lk1, ..., Map<String,Object> Var) {
    // (output's column expressions + filter folded in; return null if filter rejects)
    Object[] row = new Object[N];
    row[0] = ...;
    ...
    return row;
}

// run() stays thin:
for (int i = 0; i < rowCount; i++) {
    try {
        RowWrapper main_row = buildRowWrapper(inputRoot, i, "main_row");
        // ... lookup wrappers ...
        Map<String,Object> Var = new HashMap<>();
        // Var.put(...) per variable
        Object[] r1 = evalOutput_out1(i, main_row, lk1, Var);
        if (r1 != null) out1_data[out1_count++] = r1;
        // ... per active output ...
    } catch (Exception e) { ... existing error handling ... }
}
```

Implementation rules:
- Bindings (buildRowWrapper, inputRoot, context, globalMap) used only in run(). Helpers receive everything they need as arguments.
- Active outputs only (skip is_reject and inner_join_reject outputs, same as today).
- Output filter (activate_filter + filter) folds into the helper: helper returns null on filter rejection.
- die_on_error semantics unchanged -- exceptions in helpers bubble up to run()'s existing try/catch.
- Compile-once / execute-many contract (BRDG-06) unchanged -- script class still cached per component id.
- No Java bridge changes -- compileTMapScript / executeCompiledTMap API surface stays identical.

## Files involved

- src/v1/engine/components/transform/map.py -- _build_compiled_script (line 1583-1737), single source of the fix
- src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java -- read-only reference for compile contract (do not edit)
- tests/v1/engine/components/transform/test_map*.py -- add regression test for 250-column case
- May need a fixture builder for synthetic 250-column tMap configs

## Constraints

- ASCII-only logs (CLAUDE.md, memory: feedback_ascii_logging)
- Fix root cause, no defensive fallbacks (memory: feedback_fix_source_no_fallbacks)
- Regression test MUST exercise the real Java bridge (memory: feedback_test_real_bridge), not just inspect generated Groovy text
- Phase scope discipline: this is a tMap fix; do not sweep unrelated transform components

## Memory context

- Phase 5.1 fixed Java bridge Arrow type bugs and tMap closure dispatch
- Phase 5.2 fixed RELOAD_AT_EACH_ROW per-row lookup bugs (different code path; not affected by this fix)
- pandas 3.0.1 with CoW is installed at runtime
- BRDG-06 compile-once / execute-many: caches Script CLASS, not instance -- must remain intact

## Eliminated

## Evidence

- timestamp: 2026-05-07
  checked: Synthesized regression test with 1 main + 1 lookup, two outputs
    of 250 columns each (mix of passthrough + cast + lookup-string-concat
    expressions, plus 4 Var entries), executed against the real Java
    bridge.
  found: Pre-fix compileTMapScript raises
    groovyjarjarasm.asm.MethodTooLargeException: Method too large:
    Script1.run ()Ljava/lang/Object;
    Surfaces in Python as ComponentExecutionError [tMap_wide_2out]
    Failed to compile tMap script.
  implication: Hypothesis confirmed -- the monolithic run() bytecode
    crosses the JVM 64KB Code-attribute limit when the script's column
    expressions across all outputs exceed the budget.

- timestamp: 2026-05-07
  checked: After applying per-output method split to _build_compiled_script,
    re-ran the same regression test plus existing TestCompiledScriptGeneration
    tests in test_map.py.
  found: All 3 new regression tests pass (single 250-col, dual 250-col,
    filter-folded-into-helper). All 122 existing test_map.py +
    test_map_integration.py tests pass (1 skipped due to missing
    sample JSON fixture, unrelated). Three pre-existing failures in
    test_convert_type.py and test_java_component.py reproduce on the
    parent commit b98ac24 -- not caused by the fix.
  implication: Fix verified end-to-end via the real Java bridge.
    Compile-once / execute-many contract preserved (script class still
    cached per component id). Java bridge API surface unchanged.

## Resolution

root_cause: _build_compiled_script in src/v1/engine/components/transform/map.py
  emitted a single monolithic Groovy script. GroovyShell.parse() compiled
  the entire per-row body -- every active output's column-expression
  block, plus the variable block, plus row wrappers, plus the try/catch
  -- into ONE run() method on the generated Script subclass. With high
  aggregate column counts (e.g. two outputs of 250 columns of realistic
  Citi-style expressions), the run() bytecode exceeded the JVM hard
  limit of 65,535 bytes per method, triggering
  groovyjarjarasm.asm.MethodTooLargeException at GroovyShell.parse()
  time inside JavaBridge.compileTMapScript. The bug had always existed
  structurally; only surfaced now that real production Citi tMaps
  exceeded the budget.

fix: Per-output method split in _build_compiled_script. Generates one
  helper method per active output:
    def evalOutput_<name>(int i, RowWrapper main, RowWrapper lk1, ...,
                          Map<String,Object> Var) {
        if (!(<filter>)) return null;
        Object[] row = new Object[N];
        row[0] = ...;
        ...
        return row;
    }
  The row loop in run() stays thin: build wrappers, evaluate vars,
  call each evalOutput_*, route the returned Object[] (or skip on
  null filter rejection). Each helper compiles to its own JVM method
  with its own 64KB budget. Helpers receive every RowWrapper as
  parameters; routine classes / context / globalMap remain reachable
  via Groovy's Script getProperty fall-through. Filter folds into the
  helper. die_on_error semantics, BRDG-06 compile-once / execute-many
  caching contract, and the Java bridge API surface are all unchanged.
  Commit: 25f9f57 fix(tmap-method-too-large): split tMap script per
  output to fit JVM 64KB method limit
  (preceded by daad2c5 + 7a1e4fc with the failing reproducer test).

verification: Real-bridge regression suite at
  tests/v1/engine/components/transform/test_map_method_size.py: 3 new
  tests, all green post-fix; the 2-output 500-column reproducer fails
  pre-fix with MethodTooLargeException. Existing tMap suites:
  test_map.py 109/109 + test_map_integration.py 12/12 (+ 1 skipped on
  missing sample JSON, unrelated) + TestCompiledScriptGeneration class
  4/4 still green. Full transform suite: 1092 passed, 1 skipped, 1
  xfailed; 3 unrelated failures (test_convert_type pandas StringDtype,
  test_java_component executeOneTimeExpression signature mismatch with
  cached JAR) reproduce on the parent commit b98ac24 -- not regressions.

files_changed:
  - src/v1/engine/components/transform/map.py (_build_compiled_script
    refactored to emit per-output helper methods + thin run() loop)
  - tests/v1/engine/components/transform/test_map_method_size.py (new
    real-bridge regression suite)
