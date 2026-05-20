# tMap MethodTooLarge Fix — Design Spec

**Date:** 2026-05-20
**Branch:** `feature/engine-restructure`
**Status:** Approved, ready for implementation planning
**Author:** A Arun (with Claude)

---

## 1. Problem

The tMap engine component compiles a Groovy script per job (cached by `component_id`) and executes it via Py4J + Arrow. Today the emitter in `src/v1/engine/components/transform/map/map_compiled_script.py` produces a single script whose entire body — row loop, variable assignments, all output column assignments, try/catch — lives in Groovy's `run()` method. Groovy compiles `run()` to a single Java method.

The JVM specification (JVMS §4.7.3) limits any method's `Code` attribute to 65535 bytes. For wide tMap outputs with long expressions — the manager's failing case was one output × 180 columns × 200-5000 chars per expression, totaling on the order of 900KB of source — the emitted `run()` method busts the limit and Groovy compilation fails with `MethodTooLargeException` thrown from the bundled ASM `MethodWriter`.

This blocks production execution of the failing job and any future tMap job above the same width × complexity threshold.

## 2. Prior art and research grounding

Four parallel research subagents surveyed how comparable projects handle the same JVM limit. Key findings:

- **Apache Spark Catalyst/Tungsten WholeStageCodegen** uses two layered mitigations: predictive source-char splitting (`CodeGenerator.splitExpressions`, default `methodSplitThreshold = 1024` chars) into helper methods on the same class, plus a post-compile bytecode-measurement fallback (`hugeMethodLimit = 65535`) that drops to interpreted execution. `CodeGenerator.scala:929`, `WholeStageCodegenExec.scala:738-761`. Spilling to a private inner class when the outer class itself grows beyond 1MB.
- **Talend Open Studio** has no splitting logic in its `.javajet` code emitters; users hit this routinely (TDI-22059, TDI-4569, community 2222720 et al.) and the only documented answer is "redesign the job" — chain smaller tMaps, split subjobs, route via child jobs. Our 180-col case is past what Talend can compile.
- **Kotlin and Scala compilers** fail reactively (no in-compiler split); they push the burden to the source-emitter via local-def lifting. Scala's `maxJVMMethodSize = 65535` is used only to suppress inlining, not to split user code.
- **ANTLR4** predictively splits the serialized ATN string (issue #76, fixed 4.1) but not rule method bodies.
- **Drools** structurally avoids the limit by emitting each rule constraint and consequence as a separate lambda externalized to a singleton enum.
- **Groovy itself** has no built-in splitting. But: each closure (`def x = { ... }`) compiles to a synthetic inner class named `Script1$_run_closureN` with its own `doCall(...)` method — each one gets its own fresh 64KB budget. **This is the bytecode-level escape hatch from `run()`'s limit.**
- **Jenkins** ships exactly this pattern in production: `pipeline-model-definition-plugin`'s `SCRIPT_SPLITTING_TRANSFORMATION` (JENKINS-37984) wraps user expressions in generated closures to fix `MethodTooLargeException` on Declarative Pipeline scripts. Same JVM/Groovy stack, same problem, same fix — direct production precedent.
- **Universal pattern across all surveyed projects**: pre-split in the source emitter, target well under 64KB; no library auto-splits.

## 3. Solution overview

Rewrite the tMap Groovy emitter to always emit closure-chunked scripts. The row-loop body's heavy lifting (variable assignments, output column assignments) is split into Groovy closures defined at the top of `run()`, each chunked to stay well under the per-method bytecode limit. `run()` becomes a thin shell that builds row wrappers and dispatches to the closures in sequence.

**Why closures, not methods.** Closures inherit script-level scope and Groovy `Binding` lookup automatically; script-level `def` methods would lose visibility into `run()`'s `def`-locals. Closures match the Jenkins production precedent. Plain `def closure = {...}` inside `run()` allocates closure objects once per `run()` call — at our scale (one `run()` per 50K-row chunk, ~10 closures total), this is irrelevant overhead.

**Why always-split, not threshold-gated.** A single code path is easier to reason about, test, and explain. Spark, Jenkins, and Drools all picked structural always-split over conditional. Closure dispatch overhead is ~10ns × ~10 chunks per row × 1.5M rows = ~150ms total, well within noise for a multi-minute ETL pass.

## 4. Architecture

### 4.1 Scope of change

**Touched files:**
- `src/v1/engine/components/transform/map/map_compiled_script.py` — both `build_active_script` and `build_reject_script` are rewritten to emit closure-chunked output via a shared internal helper.

**Untouched files (verified):**
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` — no Java-side changes.
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java` — no changes.
- `src/v1/java_bridge/bridge.py` — no Python bridge-client changes.
- `src/v1/engine/components/transform/map/map_component.py`, `map_config.py`, `map_joins.py`, `map_reject_routing.py`, `map_bridge_sync.py` — no changes.
- The `__errors__` DataFrame contract (columns `rowIndex`, `errorMessage`, `errorStackTrace`) — preserved exactly.
- The Arrow IPC result-map shape (`{output_name: arrowBytes}`) — preserved exactly.

**Out of scope (deliberate YAGNI):**
- No post-compile bytecode-measurement fallback (Spark's `hugeMethodLimit`). Adds two-pass compile complexity for a failure mode the predictive emitter is sized to avoid by 8×.
- No per-closure error-attribution wrapper that re-throws with output/column context. The recent debug-logging work already surfaces the underlying exception message + stack trace; the synthetic closure-class frame in the stack is transparent to users.
- No auto-extraction of huge expressions into temp `Var`s. Breaks Talend-semantic identicality in subtle ways (operator precedence, side-effect ordering, null-safety).

### 4.2 Two configuration constants

Added at module top of `map_compiled_script.py`:

```python
_CHUNK_TARGET_CHARS = 8000
# Target emitted-source size per closure. Matches Spark's JIT-inlining cutoff
# (CodeGenerator.scala:1447 DEFAULT_JVM_HUGE_METHOD_LIMIT). Provides ~8x
# headroom under the 64KB JVM per-method bytecode limit.

_SINGLE_EXPR_HARD_CAP = 50000
# Maximum emitted size of a single column or variable expression. If any
# single emitted statement exceeds this, the emitter raises ConfigurationError
# before the script ever reaches the Java bridge.
```

### 4.3 Chunking algorithm

Single helper function:

```python
def _chunk_emitted_lines(
    lines: list[str],
    section_label: str,
    component_id: str,
) -> list[list[str]]:
    """Group emitted lines into chunks so each chunk's total emitted-char
    length stays under _CHUNK_TARGET_CHARS.

    Each line is one full statement (`tempRow[j] = expr;` or
    `Var.put("name", expr);`); lines are never split mid-statement.

    If a single line exceeds _CHUNK_TARGET_CHARS, that line gets its own
    chunk by itself (still safe — single-line chunks stay under the JVM
    limit unless the line is enormous).

    If a single line exceeds _SINGLE_EXPR_HARD_CAP, raises ConfigurationError
    with section_label, component_id, and actual line size.
    """
```

Algorithm:
1. Walk `lines` left-to-right, accumulating per-chunk char total.
2. Before appending each line, check `len(line) > _SINGLE_EXPR_HARD_CAP` → raise.
3. If `current_chunk_chars + len(line) > _CHUNK_TARGET_CHARS` and current chunk is non-empty: flush, start new chunk.
4. Append line, increment running total.
5. After loop: flush final non-empty chunk.

Return value: list of chunks (each chunk is a list of line strings).

### 4.4 Closure naming

Globally unique within a script, identifiable in stack traces:
- Active output columns: `${output_name}_chunk${n}` (e.g. `out1_chunk0`, `out1_chunk1`)
- Variables: `vars_chunk${n}`
- Reject output columns: `${output_name}_reject_chunk${n}`

### 4.5 Closure signature (explicit params)

All closures use explicit-params signatures. No reliance on enclosing-scope variable capture beyond the script-level Binding (`context`, `globalMap`, `routines.*`).

- **Variable chunks:** `{ int i, RowWrapper main, RowWrapper lk1, ..., RowWrapper lkN, Map Var -> ... }`
- **Output column chunks (active and reject):** `{ int i, RowWrapper main, RowWrapper lk1, ..., RowWrapper lkN, Map Var, Object[] tempRow -> ... }`

`Var` is a `HashMap<String, Object>` mutated by reference. `tempRow` is an `Object[]` mutated by reference. The row loop owns commits (`out1_data[out1_count++] = tempRow`) and the `matchedAny` flag — closures populate state only.

### 4.6 Generated script shape

```groovy
import java.util.*;
import com.citi.gru.etl.RowWrapper;

// ---- Closures (defined once, called from row loop) ----

def vars_chunk0 = { int i, RowWrapper row1, RowWrapper lkp1, Map Var ->
    Var.put("v1", <expr>);
    Var.put("v2", Var.get("v1") + lkp1.get("x"));
};

def out1_chunk0 = { int i, RowWrapper row1, RowWrapper lkp1, Map Var, Object[] tempRow ->
    tempRow[0]  = <expr>;
    tempRow[1]  = <expr>;
    // ... approximately 90 columns, ~7800 chars of emitted source
};

def out1_chunk1 = { int i, RowWrapper row1, RowWrapper lkp1, Map Var, Object[] tempRow ->
    tempRow[90]  = <expr>;
    tempRow[91]  = <expr>;
    // ... remaining columns
};

// ---- Output buffers (declared once outside loop) ----

Object[][] out1_data = new Object[rowCount][180];
int out1_count = 0;
int errorCount = 0;
Map<Integer, String> errorMap = new HashMap<>();
Map<Integer, String> stackTraceMap = new HashMap<>();

// ---- Row loop ----

for (int i = 0; i < rowCount; i++) {
    try {
        RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1");
        RowWrapper lkp1 = buildRowWrapper(inputRoot, i, "lkp1");

        try {
            Map<String, Object> Var = new HashMap<>();
            vars_chunk0.call(i, row1, lkp1, Var);

            boolean matchedAny = false;

            // Active output: out1
            if (<filter_expr>) {
                Object[] out1_tempRow = new Object[180];
                out1_chunk0.call(i, row1, lkp1, Var, out1_tempRow);
                out1_chunk1.call(i, row1, lkp1, Var, out1_tempRow);
                out1_data[out1_count++] = out1_tempRow;
                matchedAny = true;
            }

            if (!matchedAny) {
                // is_reject outputs populate and commit here (unchanged shape)
            }
        } catch (Exception innerE) {
            String msg = innerE.getMessage() != null ? innerE.getMessage() : innerE.toString();
            java.io.StringWriter sw = new java.io.StringWriter();
            innerE.printStackTrace(new java.io.PrintWriter(sw));
            errorCount++;
            errorMap.put(i, msg);
            stackTraceMap.put(i, sw.toString());
        }
    } catch (Exception outerE) {
        String msg = outerE.getMessage() != null ? outerE.getMessage() : outerE.toString();
        throw new RuntimeException("Error at row " + i + ": " + msg, outerE);
    }
}

// ---- Results assembly (unchanged from today) ----

Map<String, Map<String, Object>> results = new HashMap<>();
Map<String, Object> out1_result = new HashMap<>();
out1_result.put("data", out1_data);
out1_result.put("count", out1_count);
results.put("out1", out1_result);
// __errors__ assembly preserved exactly
return results;
```

### 4.7 Reject script symmetry

`build_reject_script` applies the same chunking algorithm to inner_join_reject outputs. Reject closures use the `${name}_reject_chunk${n}` naming. The two emitters share the chunking helper (`_chunk_emitted_lines`) and per-section emitters; only their per-section composition differs (reject script has no variables, no filters, no is_reject routing, no try/catch — strictly fewer regions than active).

When no `inner_join_reject` outputs exist, `build_reject_script` still returns the trivial empty-results script unchanged from today.

## 5. Filter handling

Filter expressions stay inline in the row loop's `if (<filter_expr>) { ... }` — they are typically short (one boolean) and don't accumulate column-by-column. If any single filter expression exceeds `_CHUNK_TARGET_CHARS`, it is hoisted into a single-expression closure defined alongside the other closures at the top of `run()` and called from the `if`:

```groovy
// Defined at top of run() with the other chunks:
def out1_filter = { int i, RowWrapper row1, RowWrapper lkp1, Map Var ->
    return <huge filter expr>;
};

// In the row loop:
if (out1_filter.call(i, row1, lkp1, Var)) {
    // ...
}
```

If any single filter expression exceeds `_SINGLE_EXPR_HARD_CAP`, the emitter raises `ConfigurationError` with the offending output name. Same hard-cap rule as column expressions.

## 6. Error handling

### 6.1 Runtime errors

Stack traces from closures include a synthetic frame `Script1$_run_closureN.doCall(Script1.groovy:XX)` before bubbling to the row-level try/catch. The `errorMessage` (original exception's `getMessage()`) is unchanged. The recent debug-logging work surfaces `__errors__` rows with WARN-level summaries and DEBUG-level stack traces — that surfacing logic operates on the DataFrame contract (`rowIndex`, `errorMessage`, `errorStackTrace`), which is preserved exactly.

No per-closure try/catch wrappers. The synthetic frame is transparent to user debugging.

### 6.2 Emit-time errors

The emitter performs one validation pass before returning the script source:
- Any single emitted line exceeds `_SINGLE_EXPR_HARD_CAP` → raise `ConfigurationError` with:
  ```
  f"tMap component '{component_id}': {section_label} expression "
  f"is {actual_chars} chars, exceeds the {_SINGLE_EXPR_HARD_CAP}-char limit. "
  f"Split the expression into a Var or reduce its size."
  ```
- Error fires before the script reaches the Java bridge.

## 7. Caching invariants

The bridge caches compiled Script classes keyed by `component_id` in `JavaBridge.compiledScriptClasses` (`JavaBridge.java:64`). With the new emitter:
- Same `MapConfig` produces byte-identical script source (the chunking helper is deterministic given the line list and threshold).
- Cached class survives across `execute_compiled_tmap_chunked` calls as today.
- If a tMap config changes such that chunk boundaries shift, the new script is recompiled and the cached class is replaced under the same `component_id` — current cache behavior.

No cache-key changes. No cache-invalidation logic needed.

## 8. Performance characteristics

**Memory.**
- Each closure compiles to one synthetic inner class (~few KB of bytecode per closure).
- One closure instance per `def`-declaration per `run()` invocation. Approximately 10 closures × `tens of bytes` per instance = ~1KB per `run()` call. Bridge calls `run()` once per 50K-row chunk; per-million-row job that is ~20 `run()` invocations → ~20KB transient allocation. Trivially recycled by Eden-space GC.

**CPU.**
- Closure dispatch via `chunk0.call(...)` is one virtual method call on the closure object plus reflective param dispatch. ~10ns per call.
- Approximately 10 closure calls per row × 1.5M rows = 15M extra calls = ~150ms total over the job. Within timing-log noise.
- Each closure stays under the HotSpot JIT inlining threshold (8KB), so all chunks remain inlineable by the C2 compiler.

**Compile time.**
- One `GroovyShell.parse` per component, as today. Closure-bearing source compiles in roughly the same wall-time as today's single-method source — Groovy's compiler walks the AST once either way. The closure approach adds N synthetic inner-class definitions but each is small.

## 9. Testing strategy

### 9.1 Layer 1 — Unit tests (no JVM)

New file: `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py`.

Cases:
- `_chunk_emitted_lines` correctness across synthetic line-list size distributions (no-op for empty list, single chunk for small list, multi-chunk at expected boundaries).
- Single-line-exceeds-target (>8KB, <50KB): line gets its own chunk; no error.
- Single-line-exceeds-hard-cap (>50KB): raises `ConfigurationError` with section_label, component_id, actual_size.
- Closure signature emission: snapshot-tested source for small, medium, large configs — asserts closure names, param lists, and call-site dispatch order.
- Reject-script chunking: same algorithm produces correct `${name}_reject_chunk${n}` naming.
- Variable chunking: vars-only section produces `vars_chunk${n}` closures.
- Filter hoisting: filter expression >8KB becomes a closure call; filter >50KB raises ConfigurationError.

### 9.2 Layer 2 — Live-bridge integration tests (`@pytest.mark.java`)

New file: `tests/v1/engine/components/transform/test_map_method_too_large_integration.py`.

- **Bullseye:** synthesize `MapConfig` with one output × 180 columns × ~3000 emitted chars per expression. Run through full `compile_tmap_script` + `execute_compiled_tmap_chunked` on 100 synthetic rows. Assert script compiles successfully and output DataFrame has 100 rows × 180 columns with values matching expected per-column expression evaluation.
- **Pre-regression bound:** pin a copy of the OLD `build_active_script` body in the test file as `_legacy_build_active_script`. Run the same 180×3000 fixture through it. Assert `MethodTooLargeException` (or its Py4J-bridge equivalent) is raised. This catches the false-positive case where our test fixture turned out to be too small to exercise the failure mode.
- **Identicality on existing fixtures:** for each `tests/talend_xml_samples/converted_jsons/Job_tMap_*.json` fixture (constant-key, lookup, reject), run end-to-end with both the new emitter and the pinned legacy emitter. Diff the resulting DataFrames row-for-row and column-for-column. Must be byte-identical.

### 9.3 Layer 3 — Edge cases (live bridge)

- One column whose expression is 30KB (above 8KB target, below 50KB cap): gets its own chunk, compiles, runs.
- Config with 0 variables and 0 active outputs (only `inner_join_reject`): emitter produces correct skeleton.
- Config with `catch_output_reject` enabled and a 180-col output where row 50's expression throws NPE: `__errors__` DataFrame captures row 50 with correct `rowIndex=50`, an `errorMessage` containing the NPE text, and an `errorStackTrace` that includes the synthetic closure frame. The Python-side `_make_errors_bridge` parser handles this without modification.

### 9.4 Coverage gate

Phase 14's 95% per-module floor still applies. `map_compiled_script.py` is in scope. All new branches must be covered by Layer 1 unit tests. Run the gate command from CLAUDE.md to verify.

## 10. Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Output non-identicality (closure scoping vs inline) | Medium | Layer 2 identicality tests against every existing fixture. Specifically test that closure captures of `Var` (HashMap by reference) and `tempRow` (Object[] by reference) behave identically to inline. |
| `ConfigurationError` fires on a previously-shipping job (single expression > 50KB) | Low | The error is correct behavior — that job would have failed at compile time anyway. Error message is actionable (names output and column). |
| Closure dispatch overhead at scale | Very low | Quantified at ~150ms per 1.5M-row job. Falls within the noise of existing INFO-level per-lookup timing logs; would only surface as observable overhead if the per-row tMap elapsed-time logs spiked by an order of magnitude. |
| MethodTooLargeException despite splitting (char-to-bytecode estimate wrong) | Very low | 8KB target gives 8× headroom. If it ever fires, the bridge surfaces a clear stack and we'd lower `_CHUNK_TARGET_CHARS` as a hot-fix. |

**Rollback.** Single-module change. Reverting `map_compiled_script.py` to its current contents restores prior behavior in one commit. No data migration, no cache invalidation, no schema change, no Java-side change to undo.

## 11. Sequencing for implementation

1. Build `_chunk_emitted_lines` helper + Layer 1 unit tests (red → green → refactor).
2. Per-section emitters: build `_emit_vars_chunks(cfg)`, `_emit_output_chunks(out, mode='active'|'reject')`, `_emit_filter(out)` returning `(closure_definitions: list[str], call_sites: list[str])`.
3. Rewrite `build_active_script` to compose the per-section emitters into the full script shape (Section 4.6).
4. Rewrite `build_reject_script` symmetrically (reduced set of sections — Section 4.7).
5. Add Layer 2 bullseye + pre-regression integration tests; verify both fail-old and pass-new are demonstrated.
6. Add Layer 2 identicality tests against every existing tMap fixture; verify byte-equal output.
7. Add Layer 3 edge case tests.
8. Run full coverage gate (CLAUDE.md command); confirm 95% per-module floor still passes.
9. Run pre-existing test suite to confirm no regressions outside the tMap module.

Each step gets its own commit on `feature/engine-restructure`. Step 5 is the moment we know the fix works on the failing case.

## 12. Open questions

None. All gray-area decisions resolved during the brainstorming pass (11 rounds of focused questions).

---

## Appendix A — Citation references

| Source | Purpose |
|--------|---------|
| `CodeGenerator.scala:929` (apache/spark) | Spark's `splitExpressions` — primary prior art for predictive char-based splitting |
| `CodeGenerator.scala:1447` (apache/spark) | `DEFAULT_JVM_HUGE_METHOD_LIMIT = 8000` — JIT-inlining cutoff, basis for our `_CHUNK_TARGET_CHARS` |
| `WholeStageCodegenExec.scala:738-761` (apache/spark) | Post-compile fallback path (deliberately not adopted; documented for traceability) |
| JENKINS-37984, `RuntimeASTTransformer.groovy` (jenkinsci/pipeline-model-definition-plugin) | Production precedent for closure-wrapping fix on same JVM/Groovy stack |
| `JavaTarget.java:supportsSplitParser` (antlr/antlr4) | Predictive ATN string splitting; structural-avoidance pattern |
| `BytecodeUtils.scala:maxJVMMethodSize` (scala/scala) | Confirms JVM 65535 constant; Scala uses it for inline-suppression only |
| `MaterializedLambda` (apache/incubator-kie-drools blog 2021-06) | Structural-avoidance via per-constraint lambdas |
| Talend `tMap_main.inc.javajet` (Talaxie/tdi-studio-se) | Confirms Talend itself has no splitting logic; documents the user workaround pattern |
