# tMap MethodTooLarge Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the tMap Groovy emitter (`map_compiled_script.py`) to split row-loop work into Groovy closures so 180-column / 5000-char-expression jobs compile under the JVM 64KB-per-method bytecode limit, preserving byte-identical output for all existing jobs.

**Architecture:** Single-file emitter rewrite. Per-section emit helpers (variables, output columns, optional filter hoist) each produce `(closure_definitions, dispatch_lines)` pairs. A shared `_chunk_emitted_lines` helper enforces an 8KB target per closure with a 50KB hard cap per single expression. No Java-side changes. No bridge-client changes. Output contract preserved exactly.

**Tech Stack:** Python 3.12, Groovy 3.0.21 (via Py4J + Arrow), pytest, pytest `@pytest.mark.java` for live-bridge tests.

**Spec:** `docs/superpowers/specs/2026-05-20-tmap-method-too-large-design.md`

---

## Verification gate (run after Task 12)

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

`map_compiled_script.py` is currently 100% covered. New branches must keep it >= 95%.

---

## Branch hygiene (run once before Task 1)

```bash
git status
git branch --show-current
```

Expected: working tree clean, branch is `feature/engine-restructure`. Stop and ask if either is unexpected.

---

## Task 1: Pin legacy emitter as a frozen test fixture

**Files:**
- Create: `tests/v1/engine/components/transform/test_map_method_too_large_integration.py`

Before rewriting `map_compiled_script.py`, capture the current emitter verbatim in a new test file as `_legacy_build_active_script` / `_legacy_build_reject_script` / `_legacy_groovy_escape_expression` / `_legacy_strip_marker`. This frozen snapshot is what the Task 9 pre-regression test invokes to prove the failure mode is real.

- [ ] **Step 1: Create the integration test file with the legacy snapshot**

Open the current `src/v1/engine/components/transform/map/map_compiled_script.py` and copy its full source body. Create the new test file:

```python
"""Live-bridge integration tests for tMap MethodTooLarge fix.

Holds a frozen snapshot of the legacy emitter (`_legacy_build_active_script`,
`_legacy_build_reject_script`, helpers) so the pre-regression test in this
file can prove the failure mode is real without depending on git history.

Tests in this file require a running Java bridge: `@pytest.mark.java`.
"""
from __future__ import annotations

from src.v1.engine.components.transform.map.map_config import MapConfig


# ===== Frozen legacy emitter (snapshot of map_compiled_script.py as of
# the start of this plan; never modified) =====

def _legacy_groovy_escape_expression(java_expr: str) -> str:
    # [paste current groovy_escape_expression body verbatim]
    result: list[str] = []
    in_string = False
    i = 0
    n = len(java_expr)
    while i < n:
        ch = java_expr[i]
        if not in_string:
            if ch == '"':
                in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            result.append(ch)
            result.append(java_expr[i + 1])
            i += 2
        elif ch == '"':
            in_string = False
            result.append(ch)
            i += 1
        elif ch == "$":
            result.append("\\$")
            i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def _legacy_strip_marker(expr: str) -> str:
    return expr[len("{{java}}"):] if expr.startswith("{{java}}") else expr


def _legacy_build_active_script(cfg: MapConfig) -> str:
    # [paste current build_active_script body verbatim,
    #  with `groovy_escape_expression` calls replaced by
    #  `_legacy_groovy_escape_expression` and `_strip_marker` calls
    #  replaced by `_legacy_strip_marker`]
    lines: list[str] = []
    lines.append("import java.util.*;")
    lines.append("import com.citi.gru.etl.RowWrapper;")
    lines.append("")
    active_outputs = [
        o for o in cfg.outputs
        if not o.is_reject and not o.inner_join_reject and not o.catch_output_reject
    ]
    is_reject_outputs = [o for o in cfg.outputs if o.is_reject]
    catch_outputs = [o for o in cfg.outputs if o.catch_output_reject]
    has_error_tracking = (not cfg.die_on_error) or bool(catch_outputs)
    for out in active_outputs + is_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    if has_error_tracking:
        lines.append("int errorCount = 0;")
        lines.append("Map<Integer, String> errorMap = new HashMap<>();")
        lines.append("Map<Integer, String> stackTraceMap = new HashMap<>();")
    lines.append("")
    lines.append("for (int i = 0; i < rowCount; i++) {")
    lines.append("    try {")
    main_name = cfg.main.name
    lines.append(f'        RowWrapper {main_name} = buildRowWrapper(inputRoot, i, "{main_name}");')
    for lk in cfg.lookups:
        lines.append(f'        RowWrapper {lk.name} = buildRowWrapper(inputRoot, i, "{lk.name}");')
    lines.append("")
    if has_error_tracking:
        lines.append("        try {")
        body_indent = "            "
    else:
        body_indent = "        "
    lines.append(f"{body_indent}Map<String, Object> Var = new HashMap<>();")
    for v in cfg.variables:
        expr = _legacy_groovy_escape_expression(_legacy_strip_marker(v.expression)) or "null"
        lines.append(f'{body_indent}Var.put("{v.name}", {expr});')
    lines.append("")
    if is_reject_outputs:
        lines.append(f"{body_indent}boolean matchedAny = false;")
    for out in active_outputs:
        ncols = len(out.columns)
        lines.append(f"{body_indent}// Active output: {out.name}")
        if out.activate_filter and out.filter:
            filter_expr = _legacy_groovy_escape_expression(_legacy_strip_marker(out.filter))
            lines.append(f"{body_indent}if ({filter_expr}) {{")
        else:
            lines.append(f"{body_indent}{{")
        inner = body_indent + "    "
        lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
        for j, col in enumerate(out.columns):
            expr = _legacy_groovy_escape_expression(_legacy_strip_marker(col.expression)) or "null"
            lines.append(f"{inner}{out.name}_tempRow[{j}] = {expr};")
        if is_reject_outputs:
            lines.append(f"{inner}matchedAny = true;")
        lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")
    lines.append("")
    if is_reject_outputs:
        lines.append(f"{body_indent}if (!matchedAny) {{")
        for out in is_reject_outputs:
            ncols = len(out.columns)
            inner = body_indent + "    "
            lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
            for j, col in enumerate(out.columns):
                expr = _legacy_groovy_escape_expression(_legacy_strip_marker(col.expression)) or "null"
                lines.append(f"{inner}{out.name}_tempRow[{j}] = {expr};")
            lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")
    if has_error_tracking:
        lines.append("        } catch (Exception innerE) {")
        lines.append("            String msg = innerE.getMessage() != null ? innerE.getMessage() : innerE.toString();")
        lines.append("            java.io.StringWriter sw = new java.io.StringWriter();")
        lines.append("            innerE.printStackTrace(new java.io.PrintWriter(sw));")
        lines.append("            errorCount++;")
        lines.append("            errorMap.put(i, msg);")
        lines.append("            stackTraceMap.put(i, sw.toString());")
        lines.append("        }")
    lines.append("    } catch (Exception outerE) {")
    lines.append("        String msg = outerE.getMessage() != null ? outerE.getMessage() : outerE.toString();")
    lines.append('        throw new RuntimeException("Error at row " + i + ": " + msg, outerE);')
    lines.append("    }")
    lines.append("}")
    lines.append("")
    lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
    for out in active_outputs + is_reject_outputs:
        lines.append(f"Map<String, Object> {out.name}_result = new HashMap<>();")
        lines.append(f'{out.name}_result.put("data", {out.name}_data);')
        lines.append(f'{out.name}_result.put("count", {out.name}_count);')
        lines.append(f'results.put("{out.name}", {out.name}_result);')
    if has_error_tracking:
        lines.append("Map<String, Object> errorInfo = new HashMap<>();")
        lines.append('errorInfo.put("count", errorCount);')
        lines.append('errorInfo.put("indices", new ArrayList<>(errorMap.keySet()));')
        lines.append('errorInfo.put("messages", errorMap);')
        lines.append('errorInfo.put("stackTraces", stackTraceMap);')
        lines.append('results.put("__errors__", errorInfo);')
    lines.append("return results;")
    return "\n".join(lines)


def _legacy_build_reject_script(cfg: MapConfig) -> str:
    # [paste current build_reject_script body verbatim,
    #  with helpers swapped to legacy versions]
    inner_reject_outputs = [o for o in cfg.outputs if o.inner_join_reject]
    lines: list[str] = [
        "import java.util.*;",
        "import com.citi.gru.etl.RowWrapper;",
        "",
    ]
    if not inner_reject_outputs:
        lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
        lines.append("return results;")
        return "\n".join(lines)
    for out in inner_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    lines.append("")
    lines.append("for (int i = 0; i < rowCount; i++) {")
    main_name = cfg.main.name
    lines.append(f'    RowWrapper {main_name} = buildRowWrapper(inputRoot, i, "{main_name}");')
    for lk in cfg.lookups:
        lines.append(f'    RowWrapper {lk.name} = buildRowWrapper(inputRoot, i, "{lk.name}");')
    lines.append("")
    for out in inner_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"    Object[] {out.name}_tempRow = new Object[{ncols}];")
        for j, col in enumerate(out.columns):
            expr = _legacy_groovy_escape_expression(_legacy_strip_marker(col.expression)) or "null"
            lines.append(f"    {out.name}_tempRow[{j}] = {expr};")
        lines.append(f"    {out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
    lines.append("}")
    lines.append("")
    lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
    for out in inner_reject_outputs:
        lines.append(f"Map<String, Object> {out.name}_result = new HashMap<>();")
        lines.append(f'{out.name}_result.put("data", {out.name}_data);')
        lines.append(f'{out.name}_result.put("count", {out.name}_count);')
        lines.append(f'results.put("{out.name}", {out.name}_result);')
    lines.append("return results;")
    return "\n".join(lines)


# ===== Sanity test that the snapshot matches the current emitter
# (will be deleted in Task 9 when we intentionally diverge) =====

def test_legacy_snapshot_matches_current_active_emitter():
    """At the start of this plan, the legacy snapshot must be a verbatim
    copy of the current emitter. This test will be deleted in Task 9
    when the active emitter is rewritten and the two intentionally diverge.
    """
    from src.v1.engine.components.transform.map.map_compiled_script import (
        build_active_script,
    )
    from src.v1.engine.components.transform.map.map_config import parse_config

    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "out", "is_reject": False, "inner_join_reject": False,
            "catch_output_reject": False, "filter": "", "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
        }],
        "die_on_error": True,
    }
    cfg = parse_config(raw)
    assert _legacy_build_active_script(cfg) == build_active_script(cfg)


def test_legacy_snapshot_matches_current_reject_emitter():
    from src.v1.engine.components.transform.map.map_compiled_script import (
        build_reject_script,
    )
    from src.v1.engine.components.transform.map.map_config import parse_config

    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "rej", "is_reject": False, "inner_join_reject": True,
            "catch_output_reject": False, "filter": "", "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1.id", "type": "int"}],
        }],
        "die_on_error": True,
    }
    cfg = parse_config(raw)
    assert _legacy_build_reject_script(cfg) == build_reject_script(cfg)
```

- [ ] **Step 2: Run the snapshot sanity tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_method_too_large_integration.py::test_legacy_snapshot_matches_current_active_emitter tests/v1/engine/components/transform/test_map_method_too_large_integration.py::test_legacy_snapshot_matches_current_reject_emitter -v
```

Expected: 2 passed. If either fails, the snapshot text was not pasted verbatim — fix the snapshot to match `src/v1/engine/components/transform/map/map_compiled_script.py` exactly.

- [ ] **Step 3: Commit**

```bash
git add tests/v1/engine/components/transform/test_map_method_too_large_integration.py
git commit -m "$(cat <<'EOF'
test(tmap): pin legacy emitter snapshot for MethodTooLarge regression test

Captures current build_active_script / build_reject_script verbatim
into the integration test file. The Task 9 pre-regression test will
use this snapshot to prove that the 180-col / 5000-char expression
case really did fail before the closure-chunked rewrite.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Module constants + chunking helper

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py:1-78` (add constants + helper)
- Create: `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py`

The `_chunk_emitted_lines` helper is the heart of the new emitter. Pure function, fully unit-tested before anything else.

- [ ] **Step 1: Write failing tests for the chunking helper**

Create `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py`:

```python
"""Unit tests for the line-chunking helper in map_compiled_script."""
import pytest

from src.v1.engine.components.transform.map.map_compiled_script import (
    _CHUNK_TARGET_CHARS,
    _SINGLE_EXPR_HARD_CAP,
    _chunk_emitted_lines,
)
from src.v1.engine.exceptions import ConfigurationError


def test_empty_lines_returns_empty_chunks():
    assert _chunk_emitted_lines([], section_label="vars", component_id="tMap_1") == []


def test_single_small_line_returns_one_chunk():
    lines = ['Var.put("a", 1);']
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    assert chunks == [lines]


def test_lines_under_target_stay_in_one_chunk():
    lines = ['Var.put("a", 1);'] * 10  # ~160 chars total
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    assert len(chunks) == 1
    assert chunks[0] == lines


def test_lines_over_target_split_into_multiple_chunks():
    # Each line is ~100 chars; with target=8000, expect ~80 lines per chunk
    line = "x" * 100  # 100-char line
    lines = [line] * 200  # 20,000 total chars; expect ~3 chunks
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    assert len(chunks) >= 2, f"Expected multiple chunks for 20KB of lines, got {len(chunks)}"
    # No chunk exceeds the target by more than one line's worth
    for chunk in chunks:
        total = sum(len(l) for l in chunk)
        assert total <= _CHUNK_TARGET_CHARS + len(line), (
            f"Chunk total {total} exceeds target {_CHUNK_TARGET_CHARS} + slack"
        )


def test_single_oversized_line_gets_own_chunk_no_error():
    # One 9KB line is over the 8KB target but under the 50KB hard cap
    over_target = "x" * 9000
    small = "y" * 100
    lines = [small, over_target, small]
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    # The oversized line ends up as the sole content of its chunk
    chunk_with_big_line = next(
        (c for c in chunks if any(len(l) > _CHUNK_TARGET_CHARS for l in c)),
        None,
    )
    assert chunk_with_big_line is not None
    assert len(chunk_with_big_line) == 1
    assert chunk_with_big_line[0] == over_target


def test_single_line_over_hard_cap_raises_configuration_error():
    over_cap = "x" * (_SINGLE_EXPR_HARD_CAP + 1)
    with pytest.raises(ConfigurationError) as exc:
        _chunk_emitted_lines([over_cap], section_label="output 'out1' column 'col_42'",
                             component_id="tMap_7")
    msg = str(exc.value)
    assert "tMap_7" in msg
    assert "output 'out1' column 'col_42'" in msg
    assert str(_SINGLE_EXPR_HARD_CAP) in msg


def test_chunk_boundary_only_breaks_between_lines_never_mid_line():
    # Construct lines such that the cumulative sum lands exactly at the
    # boundary at line 5: 5 lines * 1700 chars = 8500, > 8000 target.
    lines = ["a" * 1700 for _ in range(5)] + ["b" * 100 for _ in range(5)]
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    # Every line must appear exactly once, in order, and only at a chunk break
    flattened = [l for c in chunks for l in c]
    assert flattened == lines


def test_constants_have_expected_values():
    # Sanity: spec section 4.2 lists these constants
    assert _CHUNK_TARGET_CHARS == 8000
    assert _SINGLE_EXPR_HARD_CAP == 50000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v
```

Expected: All FAIL with `ImportError: cannot import name '_chunk_emitted_lines'` (and `_CHUNK_TARGET_CHARS`, `_SINGLE_EXPR_HARD_CAP`).

- [ ] **Step 3: Add module constants + helper to `map_compiled_script.py`**

Edit `src/v1/engine/components/transform/map/map_compiled_script.py` — add after the existing module docstring (line 16), before the `from __future__` import block:

```python
from __future__ import annotations

from .map_config import MapConfig
from src.v1.engine.exceptions import ConfigurationError


# ---------------------------------------------------------------
# Chunking constants (see spec section 4.2)
# ---------------------------------------------------------------

_CHUNK_TARGET_CHARS = 8000
# Target emitted-source size per closure. Matches Spark's JIT-inlining cutoff
# (CodeGenerator.scala:1447 DEFAULT_JVM_HUGE_METHOD_LIMIT). Provides ~8x
# headroom under the 64KB JVM per-method bytecode limit.

_SINGLE_EXPR_HARD_CAP = 50000
# Maximum emitted size of a single column or variable expression. If any
# single emitted statement exceeds this, the emitter raises ConfigurationError
# before the script ever reaches the Java bridge.


def _chunk_emitted_lines(
    lines: list[str],
    section_label: str,
    component_id: str,
) -> list[list[str]]:
    """Group emitted lines into chunks under _CHUNK_TARGET_CHARS each.

    Each line must be one full Groovy statement (e.g. ``tempRow[j] = expr;``);
    lines are never split mid-statement. If a single line exceeds the
    target, it gets its own chunk by itself. If a single line exceeds
    _SINGLE_EXPR_HARD_CAP, ConfigurationError is raised.

    Args:
        lines: emitted statement strings for one section.
        section_label: descriptive label for error messages
            (e.g. "output 'out1' column 'col_42'").
        component_id: tMap component id for error messages.

    Returns:
        List of chunks; each chunk is a list of statement strings.

    Raises:
        ConfigurationError: if any single line exceeds _SINGLE_EXPR_HARD_CAP.
    """
    if not lines:
        return []

    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0

    for line in lines:
        line_len = len(line)
        if line_len > _SINGLE_EXPR_HARD_CAP:
            raise ConfigurationError(
                f"tMap component '{component_id}': {section_label} expression "
                f"is {line_len} chars, exceeds the {_SINGLE_EXPR_HARD_CAP}-char limit. "
                f"Split the expression into a Var or reduce its size."
            )
        if current and current_chars + line_len > _CHUNK_TARGET_CHARS:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(line)
        current_chars += line_len

    if current:
        chunks.append(current)

    return chunks
```

(Keep the existing `groovy_escape_expression` and `_strip_marker` functions; they stay used.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py
git commit -m "$(cat <<'EOF'
feat(tmap): add _chunk_emitted_lines helper + module constants

Pure function that groups emitted Groovy statement lines into chunks
each under _CHUNK_TARGET_CHARS (8000), enforcing _SINGLE_EXPR_HARD_CAP
(50000) per single statement.

Spec section 4.2 + 4.3.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Per-section emitter for variables

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py` (add `_emit_vars_section`)
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py` (append)

The variables section is the simplest — no filter, no tempRow, just `Var.put(...)` lines. Build a per-section emitter that returns `(closure_defs, dispatch_lines)`.

- [ ] **Step 1: Write failing tests**

Append to `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py`:

```python
# ===== _emit_vars_section =====

from src.v1.engine.components.transform.map.map_compiled_script import (
    _emit_vars_section,
)
from src.v1.engine.components.transform.map.map_config import parse_config


def _cfg_with_vars(var_specs):
    """var_specs: list of (name, expression) pairs."""
    raw = {
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "lkp1", "join_keys": [],
                "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE",
            }],
        },
        "variables": [
            {"name": n, "expression": e, "type": "str"}
            for n, e in var_specs
        ],
        "outputs": [{
            "name": "out", "columns": [
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
        }],
    }
    return parse_config(raw)


def test_emit_vars_section_empty_returns_no_closures():
    cfg = _cfg_with_vars([])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    assert closure_defs == []
    assert dispatch_lines == []


def test_emit_vars_section_single_var_one_closure():
    cfg = _cfg_with_vars([("v1", "row1.amount + 1")])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    # One closure definition starting with `def vars_chunk0 = {`
    assert any("def vars_chunk0 =" in d for d in closure_defs)
    # One dispatch call site
    assert dispatch_lines == ['vars_chunk0.call(i, row1, lkp1, Var);']
    # Closure body contains the Var.put line
    full = "\n".join(closure_defs)
    assert 'Var.put("v1", row1.amount + 1);' in full


def test_emit_vars_section_many_small_vars_one_closure():
    # 10 vars of ~50 chars each = ~500 chars, well under 8000 target
    cfg = _cfg_with_vars([(f"v{i}", f"row1.x{i}") for i in range(10)])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    # All in one closure
    closure_def_count = sum(1 for d in closure_defs if "def vars_chunk" in d)
    assert closure_def_count == 1
    assert dispatch_lines == ['vars_chunk0.call(i, row1, lkp1, Var);']


def test_emit_vars_section_large_vars_split_into_multiple_closures():
    # 200 vars with ~80-char expressions = ~16KB; expect 2 or 3 closures
    cfg = _cfg_with_vars([(f"v{i}", "row1." + ("x" * 70)) for i in range(200)])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    closure_def_count = sum(1 for d in closure_defs if "def vars_chunk" in d)
    assert closure_def_count >= 2, f"Expected >=2 closures, got {closure_def_count}"
    # One dispatch line per closure, in order
    assert len(dispatch_lines) == closure_def_count
    for i, line in enumerate(dispatch_lines):
        assert f"vars_chunk{i}.call(i, row1, lkp1, Var);" == line


def test_emit_vars_section_signature_includes_all_lookups():
    raw = {
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [
                {"name": "lkpA", "join_keys": []},
                {"name": "lkpB", "join_keys": []},
            ],
        },
        "variables": [{"name": "v", "expression": "1", "type": "str"}],
        "outputs": [{"name": "out", "columns": [{"name": "id", "expression": "1", "type": "int"}]}],
    }
    cfg = parse_config(raw)
    closure_defs, _ = _emit_vars_section(cfg, component_id="tMap_1")
    full = "\n".join(closure_defs)
    # Closure signature lists both lookups
    assert "RowWrapper lkpA" in full
    assert "RowWrapper lkpB" in full


def test_emit_vars_section_strips_java_marker_and_escapes_dollar():
    cfg = _cfg_with_vars([("v1", '{{java}}"$total"')])
    closure_defs, _ = _emit_vars_section(cfg, component_id="tMap_1")
    full = "\n".join(closure_defs)
    # Marker stripped, $ escaped
    assert 'Var.put("v1", "\\$total");' in full
    assert "{{java}}" not in full
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v -k "emit_vars_section"
```

Expected: All FAIL with `ImportError: cannot import name '_emit_vars_section'`.

- [ ] **Step 3: Add `_emit_vars_section` to `map_compiled_script.py`**

Add after `_chunk_emitted_lines`:

```python
def _emit_vars_section(
    cfg: MapConfig,
    component_id: str,
) -> tuple[list[str], list[str]]:
    """Build the variables section: closure definitions + dispatch lines.

    Returns:
        (closure_defs, dispatch_lines)
        closure_defs: source lines defining the vars_chunk{N} closures.
        dispatch_lines: ``vars_chunk{N}.call(i, row1, lkpA, ..., Var);``
            statements to be emitted inside the row loop.

    Empty if cfg has no variables.
    """
    if not cfg.variables:
        return [], []

    # Build the per-variable emitted lines first
    var_lines: list[str] = []
    for v in cfg.variables:
        expr = groovy_escape_expression(_strip_marker(v.expression)) or "null"
        var_lines.append(f'Var.put("{v.name}", {expr});')

    # Chunk them
    chunks = _chunk_emitted_lines(
        var_lines,
        section_label="variable",
        component_id=component_id,
    )

    # Closure signature: (int i, RowWrapper main, RowWrapper lkpA, ..., Map Var)
    lookup_params = ", ".join(f"RowWrapper {lk.name}" for lk in cfg.lookups)
    if lookup_params:
        sig = f"int i, RowWrapper {cfg.main.name}, {lookup_params}, Map Var"
    else:
        sig = f"int i, RowWrapper {cfg.main.name}, Map Var"

    # Dispatch arg list: (i, main, lkpA, ..., Var)
    lookup_args = ", ".join(lk.name for lk in cfg.lookups)
    if lookup_args:
        call_args = f"i, {cfg.main.name}, {lookup_args}, Var"
    else:
        call_args = f"i, {cfg.main.name}, Var"

    closure_defs: list[str] = []
    dispatch_lines: list[str] = []
    for idx, chunk in enumerate(chunks):
        closure_defs.append(f"def vars_chunk{idx} = {{ {sig} ->")
        for line in chunk:
            closure_defs.append(f"    {line}")
        closure_defs.append("};")
        closure_defs.append("")
        dispatch_lines.append(f"vars_chunk{idx}.call({call_args});")

    return closure_defs, dispatch_lines
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v -k "emit_vars_section"
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py
git commit -m "$(cat <<'EOF'
feat(tmap): add _emit_vars_section per-section emitter

Returns (closure_defs, dispatch_lines) for the variables section.
Chunks Var.put(...) statements into vars_chunk{N} closures under
_CHUNK_TARGET_CHARS each.

Spec section 4.5 + 4.6.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Per-section emitter for output columns (works for active and reject)

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py` (add `_emit_output_section`)
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py` (append)

Output column emitter — one function reused by both active and reject passes (Section 4.7 of the spec). Takes a single `OutputCfg` and returns `(closure_defs, dispatch_lines)` writing into the output's tempRow.

- [ ] **Step 1: Write failing tests**

Append to `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py`:

```python
# ===== _emit_output_section =====

from src.v1.engine.components.transform.map.map_compiled_script import (
    _emit_output_section,
)


def _cfg_with_output(output_cols, is_reject_pass=False):
    """output_cols: list of (name, expression) pairs."""
    raw = {
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{"name": "lkp1", "join_keys": []}],
        },
        "variables": [],
        "outputs": [{
            "name": "out", "is_reject": False,
            "inner_join_reject": is_reject_pass,
            "catch_output_reject": False,
            "columns": [
                {"name": n, "expression": e, "type": "str"}
                for n, e in output_cols
            ],
        }],
    }
    return parse_config(raw)


def test_emit_output_section_small_output_one_closure():
    cfg = _cfg_with_output([("a", "row1.x"), ("b", "row1.y")])
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    assert any("def out_chunk0 =" in d for d in closure_defs)
    assert dispatch_lines == ['out_chunk0.call(i, row1, lkp1, Var, out_tempRow);']
    full = "\n".join(closure_defs)
    assert "tempRow[0] = row1.x;" in full
    assert "tempRow[1] = row1.y;" in full


def test_emit_output_section_large_output_multiple_closures():
    # 180 cols x ~50-char exprs = ~9KB; expect at least 2 closures
    cols = [(f"c{i}", f"row1.col{i} + " + ('x' * 40)) for i in range(180)]
    cfg = _cfg_with_output(cols)
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    closure_count = sum(1 for d in closure_defs if "def out_chunk" in d)
    assert closure_count >= 2, f"Expected >=2 closures for 180 cols, got {closure_count}"
    # Dispatch lines match closure count, in order
    assert len(dispatch_lines) == closure_count
    for i, line in enumerate(dispatch_lines):
        assert f"out_chunk{i}.call(i, row1, lkp1, Var, out_tempRow);" == line


def test_emit_output_section_reject_pass_uses_reject_chunk_naming():
    cfg = _cfg_with_output([("a", "row1.x")], is_reject_pass=True)
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=True,
    )
    # Reject pass uses {name}_reject_chunk{N}
    assert any("def out_reject_chunk0 =" in d for d in closure_defs)
    assert dispatch_lines == ['out_reject_chunk0.call(i, row1, lkp1, Var, out_tempRow);']


def test_emit_output_section_single_huge_expression_in_own_chunk():
    # One 9KB expression alongside two small ones
    huge = "row1.x + " + ("a" * 8990)
    cfg = _cfg_with_output([("s1", "row1.x"), ("big", huge), ("s2", "row1.y")])
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    closure_count = sum(1 for d in closure_defs if "def out_chunk" in d)
    assert closure_count >= 2, "Huge expression should force at least one chunk boundary"


def test_emit_output_section_expression_over_hard_cap_raises_with_column_name():
    over_cap = "row1.x + " + ("a" * 50000)
    cfg = _cfg_with_output([("good", "row1.y"), ("toobig", over_cap)])
    out = cfg.outputs[0]
    with pytest.raises(ConfigurationError) as exc:
        _emit_output_section(
            out, cfg, component_id="tMap_4", is_reject_pass=False,
        )
    msg = str(exc.value)
    assert "tMap_4" in msg
    assert "output 'out' column 'toobig'" in msg


def test_emit_output_section_no_lookups_signature_omits_lookup_params():
    raw = {
        "inputs": {"main": {"name": "row1"}, "lookups": []},
        "variables": [],
        "outputs": [{
            "name": "out", "columns": [{"name": "a", "expression": "row1.x", "type": "str"}],
        }],
    }
    cfg = parse_config(raw)
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    full = "\n".join(closure_defs)
    # No "RowWrapper lkp" in signature
    assert "RowWrapper lkp" not in full
    # Dispatch line has no lookup args
    assert dispatch_lines == ['out_chunk0.call(i, row1, Var, out_tempRow);']
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v -k "emit_output_section"
```

Expected: All FAIL with `ImportError: cannot import name '_emit_output_section'`.

- [ ] **Step 3: Add `_emit_output_section` to `map_compiled_script.py`**

```python
def _emit_output_section(
    out,
    cfg: MapConfig,
    component_id: str,
    is_reject_pass: bool,
) -> tuple[list[str], list[str]]:
    """Build closure definitions + dispatch lines for one output's columns.

    Args:
        out: OutputCfg for the single output to emit.
        cfg: full MapConfig (used for main + lookup names in signature).
        component_id: tMap component id for error messages.
        is_reject_pass: if True, closures are named {name}_reject_chunk{N};
            else {name}_chunk{N}.

    Returns:
        (closure_defs, dispatch_lines) -- same shape as _emit_vars_section.
    """
    # Build per-column emitted lines
    col_lines: list[str] = []
    col_labels: list[str] = []  # parallel list, used only on hard-cap error
    for j, col in enumerate(out.columns):
        expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
        col_lines.append(f"tempRow[{j}] = {expr};")
        col_labels.append(f"output '{out.name}' column '{col.name}'")

    # Pre-scan for hard-cap violations so the error names the offending column
    for line, label in zip(col_lines, col_labels):
        if len(line) > _SINGLE_EXPR_HARD_CAP:
            raise ConfigurationError(
                f"tMap component '{component_id}': {label} expression "
                f"is {len(line)} chars, exceeds the {_SINGLE_EXPR_HARD_CAP}-char limit. "
                f"Split the expression into a Var or reduce its size."
            )

    chunks = _chunk_emitted_lines(
        col_lines,
        section_label=f"output '{out.name}'",
        component_id=component_id,
    )

    suffix = "reject_chunk" if is_reject_pass else "chunk"

    # Signature: (int i, RowWrapper main, RowWrapper lkpA, ..., Map Var, Object[] tempRow)
    lookup_params = ", ".join(f"RowWrapper {lk.name}" for lk in cfg.lookups)
    if lookup_params:
        sig = f"int i, RowWrapper {cfg.main.name}, {lookup_params}, Map Var, Object[] tempRow"
    else:
        sig = f"int i, RowWrapper {cfg.main.name}, Map Var, Object[] tempRow"

    lookup_args = ", ".join(lk.name for lk in cfg.lookups)
    if lookup_args:
        call_args = f"i, {cfg.main.name}, {lookup_args}, Var, {out.name}_tempRow"
    else:
        call_args = f"i, {cfg.main.name}, Var, {out.name}_tempRow"

    closure_defs: list[str] = []
    dispatch_lines: list[str] = []
    for idx, chunk in enumerate(chunks):
        closure_name = f"{out.name}_{suffix}{idx}"
        closure_defs.append(f"def {closure_name} = {{ {sig} ->")
        for line in chunk:
            closure_defs.append(f"    {line}")
        closure_defs.append("};")
        closure_defs.append("")
        dispatch_lines.append(f"{closure_name}.call({call_args});")

    return closure_defs, dispatch_lines
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v -k "emit_output_section"
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py
git commit -m "$(cat <<'EOF'
feat(tmap): add _emit_output_section per-section emitter

One function used by both active and reject passes. Returns
(closure_defs, dispatch_lines) for one OutputCfg's column
assignments. Hard-cap violation raises ConfigurationError naming
the offending column.

Spec section 4.5 + 4.7.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Filter hoist helper

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py` (add `_emit_filter_section`)
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py` (append)

Filter expressions stay inline by default. Only when the emitted filter exceeds `_CHUNK_TARGET_CHARS` do we hoist it into a closure. Helper returns `(optional_closure_def, callable_filter_expression)`.

- [ ] **Step 1: Write failing tests**

Append to `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py`:

```python
# ===== _emit_filter_section =====

from src.v1.engine.components.transform.map.map_compiled_script import (
    _emit_filter_section,
)


def test_emit_filter_section_no_filter_returns_none_and_true():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = False
    out.filter = ""
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    assert closure_def is None
    assert expr == "true"


def test_emit_filter_section_small_filter_inline():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    out.filter = "row1.amount > 0"
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    # Inline: no closure
    assert closure_def is None
    assert expr == "row1.amount > 0"


def test_emit_filter_section_huge_filter_hoisted_to_closure():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    # 9KB filter
    out.filter = "row1.x > 0 && " + "true && " * 1200  # ~9.6KB
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    # Closure emitted
    assert closure_def is not None
    assert "def out_filter =" in closure_def
    # Callable expression dispatches to the closure
    assert expr == "out_filter.call(i, row1, lkp1, Var)"


def test_emit_filter_section_filter_over_hard_cap_raises():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    out.filter = "x" * (_SINGLE_EXPR_HARD_CAP + 100)
    with pytest.raises(ConfigurationError) as exc:
        _emit_filter_section(out, cfg, component_id="tMap_9")
    msg = str(exc.value)
    assert "tMap_9" in msg
    assert "output 'out' filter" in msg


def test_emit_filter_section_strips_java_marker_and_escapes_dollar():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    out.filter = '{{java}}"$amount" != null'
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    # Marker stripped, $ escaped in inline expression
    assert closure_def is None
    assert expr == '"\\$amount" != null'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v -k "emit_filter_section"
```

Expected: All FAIL with `ImportError: cannot import name '_emit_filter_section'`.

- [ ] **Step 3: Add `_emit_filter_section` to `map_compiled_script.py`**

```python
def _emit_filter_section(
    out,
    cfg: MapConfig,
    component_id: str,
) -> tuple[str | None, str]:
    """Build the filter for one output: inline expression or hoisted closure.

    Returns:
        (closure_def_or_None, callable_expression)
        closure_def_or_None: full closure source if filter was hoisted,
            else None.
        callable_expression: the Groovy expression to put inside the
            row loop's ``if (...)`` -- either the raw filter or a
            closure call.

    Raises:
        ConfigurationError: if the emitted filter exceeds _SINGLE_EXPR_HARD_CAP.
    """
    if not out.activate_filter or not out.filter:
        return None, "true"

    filter_src = groovy_escape_expression(_strip_marker(out.filter))

    if len(filter_src) > _SINGLE_EXPR_HARD_CAP:
        raise ConfigurationError(
            f"tMap component '{component_id}': output '{out.name}' filter "
            f"is {len(filter_src)} chars, exceeds the {_SINGLE_EXPR_HARD_CAP}-char limit. "
            f"Split the filter into a Var or reduce its size."
        )

    if len(filter_src) <= _CHUNK_TARGET_CHARS:
        return None, filter_src

    # Hoist into a closure
    lookup_params = ", ".join(f"RowWrapper {lk.name}" for lk in cfg.lookups)
    if lookup_params:
        sig = f"int i, RowWrapper {cfg.main.name}, {lookup_params}, Map Var"
    else:
        sig = f"int i, RowWrapper {cfg.main.name}, Map Var"

    lookup_args = ", ".join(lk.name for lk in cfg.lookups)
    if lookup_args:
        call_args = f"i, {cfg.main.name}, {lookup_args}, Var"
    else:
        call_args = f"i, {cfg.main.name}, Var"

    closure_name = f"{out.name}_filter"
    closure_def = (
        f"def {closure_name} = {{ {sig} ->\n"
        f"    return {filter_src};\n"
        f"}};\n"
    )

    return closure_def, f"{closure_name}.call({call_args})"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py -v -k "emit_filter_section"
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py
git commit -m "$(cat <<'EOF'
feat(tmap): add _emit_filter_section with conditional hoist

Filters under _CHUNK_TARGET_CHARS stay inline in the row loop's
if (...). Filters above it get hoisted to a closure; filters above
_SINGLE_EXPR_HARD_CAP raise ConfigurationError.

Spec section 5.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Rewrite `build_active_script`

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py:81-227` (replace `build_active_script` body)
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script.py` (update existing tests)

Compose the per-section emitters into the full active-pass script (spec section 4.6). Existing tests in `test_map_compiled_script.py` check the OLD inline shape and must be updated.

- [ ] **Step 1: Update existing tests to assert the new closure-based shape**

Open `tests/v1/engine/components/transform/map/test_map_compiled_script.py` and update each `build_active_script` test. Replace inline-shape assertions with closure-shape assertions. Update in-place (do not duplicate).

Specifically:
- `test_build_active_script_basic_includes_imports_and_buffer_decls`: imports + `Object[][] out_data` still appear at top. Buffer decls unchanged. **No change needed.**
- `test_build_active_script_basic_row_loop_shape`: change to assert `def out_chunk0 =` exists AND row loop contains `out_chunk0.call(i, row1, Var, out_tempRow);`.
- `test_build_active_script_basic_returns_results_map`: unchanged (results-map assembly is unchanged).
- `test_build_active_script_with_variables_chained`: assert `def vars_chunk0 =` exists with `Var.put("v1", row1.amount);` and `Var.put("v2", Var.get("v1") + 100);` inside; row loop dispatches `vars_chunk0.call(...)`.
- `test_build_active_script_with_filter`: small filter stays inline — assert `if (row1.amount > 0)` in row loop.
- `test_build_active_script_with_is_reject_emits_matched_any`: assert `boolean matchedAny = false;` still present at row-loop body; assert `matchedAny = true;` in the row loop body (NOT inside any closure).
- `test_build_active_script_with_catch_emits_error_tracking_and_stacktrace`: error-tracking code (errorMap, stackTraceMap) lives in run() body, not in closures. Assertions unchanged.
- `test_build_active_script_die_on_error_false_emits_error_tracking_too`: same as above.

Here are the updates as a unified diff. Apply each by editing the corresponding test function:

```python
# REPLACE the body of test_build_active_script_basic_row_loop_shape
def test_build_active_script_basic_row_loop_shape():
    cfg = parse_config(_basic_cfg())
    src = build_active_script(cfg)
    # Closure defined before row loop
    assert "def out_chunk0 =" in src
    # Closure body has tempRow assignments
    assert "tempRow[0] = row1.id;" in src
    assert 'tempRow[1] = "row_" + row1.id;' in src
    # Row loop dispatches to the closure
    assert "out_chunk0.call(i, row1, Var, out_tempRow);" in src
    # Buffer commit lives in row loop, not closure
    assert "out_data[out_count++] = out_tempRow;" in src

# REPLACE the body of test_build_active_script_with_variables_chained
def test_build_active_script_with_variables_chained():
    cfg = parse_config(_basic_cfg(with_variables=True))
    src = build_active_script(cfg)
    # Variables go into vars_chunk closure
    assert "def vars_chunk0 =" in src
    assert 'Var.put("v1", row1.amount);' in src
    assert 'Var.put("v2", Var.get("v1") + 100);' in src
    # Dispatch from row loop
    assert "vars_chunk0.call(i, row1, Var);" in src

# REPLACE the body of test_build_active_script_with_filter
def test_build_active_script_with_filter():
    cfg = parse_config(_basic_cfg(with_filter=True))
    src = build_active_script(cfg)
    # Small filter stays inline
    assert "if (row1.amount > 0) {" in src
    # No filter closure for a small filter
    assert "def out_filter =" not in src
```

(Existing test_build_active_script_with_is_reject_emits_matched_any, *_with_catch_*, *_die_on_error_* assertions still pass because matchedAny + error-tracking remain in run() body. If any sub-string assertion happens to reference the OLD inline `out_tempRow[0] = ...` shape, update it to expect closure dispatch instead.)

- [ ] **Step 2: Run the updated tests to verify they fail against the OLD emitter**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v -k "build_active_script"
```

Expected: at least the three updated tests FAIL — they assert closure-based shape that the current emitter does not produce.

- [ ] **Step 3: Rewrite `build_active_script` in `map_compiled_script.py`**

Replace the body of `build_active_script` (lines 81-227) with this composition:

```python
def build_active_script(cfg: MapConfig) -> str:
    """Build the active-pass Groovy script for a tMap.

    Closure-chunked layout (spec sections 4.6, 5, 6): variables and output
    columns are split into Groovy closures defined at top of run(); the
    row loop dispatches to closures and owns commits + matchedAny.

    Args:
        cfg: Parsed MapConfig.

    Returns:
        Groovy source string ready for compilation.
    """
    lines: list[str] = []
    component_id = cfg.label or "tMap"

    # Output classification
    active_outputs = [
        o for o in cfg.outputs
        if not o.is_reject and not o.inner_join_reject and not o.catch_output_reject
    ]
    is_reject_outputs = [o for o in cfg.outputs if o.is_reject]
    catch_outputs = [o for o in cfg.outputs if o.catch_output_reject]

    has_error_tracking = (not cfg.die_on_error) or bool(catch_outputs)

    # ---- Imports ----
    lines.append("import java.util.*;")
    lines.append("import com.citi.gru.etl.RowWrapper;")
    lines.append("")

    # ---- Closure definitions (vars + filters + output columns) ----
    vars_closure_defs, vars_dispatch = _emit_vars_section(cfg, component_id)
    lines.extend(vars_closure_defs)

    active_per_output: list[tuple[OutputCfg, str | None, str, list[str]]] = []
    # Each tuple: (out, filter_closure_def, filter_callable_expr, output_dispatch_lines)
    for out in active_outputs:
        filter_closure_def, filter_expr = _emit_filter_section(out, cfg, component_id)
        if filter_closure_def:
            lines.append(filter_closure_def.rstrip())
            lines.append("")
        out_defs, out_dispatch = _emit_output_section(
            out, cfg, component_id, is_reject_pass=False,
        )
        lines.extend(out_defs)
        active_per_output.append((out, filter_closure_def, filter_expr, out_dispatch))

    reject_per_output: list[tuple[OutputCfg, list[str]]] = []
    for out in is_reject_outputs:
        out_defs, out_dispatch = _emit_output_section(
            out, cfg, component_id, is_reject_pass=False,
        )
        lines.extend(out_defs)
        reject_per_output.append((out, out_dispatch))

    # ---- Buffer declarations ----
    for out in active_outputs + is_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    if has_error_tracking:
        lines.append("int errorCount = 0;")
        lines.append("Map<Integer, String> errorMap = new HashMap<>();")
        lines.append("Map<Integer, String> stackTraceMap = new HashMap<>();")
    lines.append("")

    # ---- Row loop ----
    lines.append("for (int i = 0; i < rowCount; i++) {")
    lines.append("    try {")
    lines.append(f'        RowWrapper {cfg.main.name} = buildRowWrapper(inputRoot, i, "{cfg.main.name}");')
    for lk in cfg.lookups:
        lines.append(f'        RowWrapper {lk.name} = buildRowWrapper(inputRoot, i, "{lk.name}");')
    lines.append("")

    if has_error_tracking:
        lines.append("        try {")
        body_indent = "            "
    else:
        body_indent = "        "

    lines.append(f"{body_indent}Map<String, Object> Var = new HashMap<>();")
    for d in vars_dispatch:
        lines.append(f"{body_indent}{d}")
    lines.append("")

    if is_reject_outputs:
        lines.append(f"{body_indent}boolean matchedAny = false;")

    # Active outputs
    for out, filter_def, filter_expr, dispatch_lines in active_per_output:
        ncols = len(out.columns)
        lines.append(f"{body_indent}// Active output: {out.name}")
        lines.append(f"{body_indent}if ({filter_expr}) {{")
        inner = body_indent + "    "
        lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
        for d in dispatch_lines:
            lines.append(f"{inner}{d}")
        if is_reject_outputs:
            lines.append(f"{inner}matchedAny = true;")
        lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")
    lines.append("")

    # is_reject routing
    if is_reject_outputs:
        lines.append(f"{body_indent}if (!matchedAny) {{")
        inner = body_indent + "    "
        for out, dispatch_lines in reject_per_output:
            ncols = len(out.columns)
            lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
            for d in dispatch_lines:
                lines.append(f"{inner}{d}")
            lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")

    # Error tracking inner catch
    if has_error_tracking:
        lines.append("        } catch (Exception innerE) {")
        lines.append("            String msg = innerE.getMessage() != null ? innerE.getMessage() : innerE.toString();")
        lines.append("            java.io.StringWriter sw = new java.io.StringWriter();")
        lines.append("            innerE.printStackTrace(new java.io.PrintWriter(sw));")
        lines.append("            errorCount++;")
        lines.append("            errorMap.put(i, msg);")
        lines.append("            stackTraceMap.put(i, sw.toString());")
        lines.append("        }")

    # Outer catch
    lines.append("    } catch (Exception outerE) {")
    lines.append("        String msg = outerE.getMessage() != null ? outerE.getMessage() : outerE.toString();")
    lines.append('        throw new RuntimeException("Error at row " + i + ": " + msg, outerE);')
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ---- Results assembly (unchanged from legacy) ----
    lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
    for out in active_outputs + is_reject_outputs:
        lines.append(f"Map<String, Object> {out.name}_result = new HashMap<>();")
        lines.append(f'{out.name}_result.put("data", {out.name}_data);')
        lines.append(f'{out.name}_result.put("count", {out.name}_count);')
        lines.append(f'results.put("{out.name}", {out.name}_result);')

    if has_error_tracking:
        lines.append("Map<String, Object> errorInfo = new HashMap<>();")
        lines.append('errorInfo.put("count", errorCount);')
        lines.append('errorInfo.put("indices", new ArrayList<>(errorMap.keySet()));')
        lines.append('errorInfo.put("messages", errorMap);')
        lines.append('errorInfo.put("stackTraces", stackTraceMap);')
        lines.append('results.put("__errors__", errorInfo);')

    lines.append("return results;")
    return "\n".join(lines)
```

Update the existing `from .map_config import MapConfig` line at the top of the file to also import `OutputCfg`:

```python
from .map_config import MapConfig, OutputCfg
```

Then in the `build_active_script` body above, replace every occurrence of `OutputCfg` with `OutputCfg`.

- [ ] **Step 4: Run all `build_active_script` tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v -k "build_active_script"
```

Expected: all `build_active_script` tests PASS (including the three updated ones).

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py tests/v1/engine/components/transform/map/test_map_compiled_script.py
git commit -m "$(cat <<'EOF'
feat(tmap): rewrite build_active_script with closure chunking

Composes _emit_vars_section + _emit_filter_section + _emit_output_section
into the full active-pass shape from spec section 4.6. Closures defined
at top of run(); row loop dispatches and owns commits + matchedAny.
__errors__ contract preserved exactly.

Existing tests updated to assert the new closure-based shape.

Spec section 4.6.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Rewrite `build_reject_script`

**Files:**
- Modify: `src/v1/engine/components/transform/map/map_compiled_script.py:230-295` (replace `build_reject_script` body)
- Modify: `tests/v1/engine/components/transform/map/test_map_compiled_script.py` (update existing reject tests)

Symmetric rewrite. Reject script has only `inner_join_reject` outputs, no variables, no filter, no try/catch.

- [ ] **Step 1: Update existing reject tests**

Open `tests/v1/engine/components/transform/map/test_map_compiled_script.py`. For each existing `test_build_reject_script_*` test, replace inline-shape assertions with closure-shape assertions:

```python
# REPLACE the body of test_build_reject_script_emits_only_inner_join_reject_outputs
def test_build_reject_script_emits_only_inner_join_reject_outputs():
    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [
            {"name": "out_active", "columns": [
                {"name": "id", "expression": "row1.id", "type": "int", "nullable": True},
            ]},
            {"name": "out_reject", "inner_join_reject": True, "columns": [
                {"name": "id", "expression": "row1.id", "type": "int", "nullable": True},
            ]},
        ],
        "die_on_error": True,
    }
    cfg = parse_config(raw)
    src = build_reject_script(cfg)
    # Active output NOT present
    assert "out_active_data" not in src
    # Reject output present with reject-pass naming
    assert "def out_reject_reject_chunk0 =" in src
    assert "out_reject_data" in src
    assert "out_reject_reject_chunk0.call(i, row1, Var, out_reject_tempRow);" in src
```

(If there are other reject tests asserting the inline `tempRow[j] = expr` shape inside the row loop, update them to assert the new closure-dispatch shape.)

- [ ] **Step 2: Run reject tests to verify they fail**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v -k "build_reject_script"
```

Expected: updated test FAILS — current emitter does not produce closure shape.

- [ ] **Step 3: Rewrite `build_reject_script`**

Replace the body of `build_reject_script` in `map_compiled_script.py`:

```python
def build_reject_script(cfg: MapConfig) -> str:
    """Build the reject-pass Groovy script for inner_join_reject outputs.

    Closure-chunked layout, symmetric with build_active_script but reduced:
    no variables, no filters, no is_reject routing, no try/catch.

    When no inner_join_reject output exists, returns a trivial
    empty-results script.

    Args:
        cfg: Parsed MapConfig.

    Returns:
        Groovy source string. Used by Map._process to compile and execute
        a second bridge pass over the reject row source.
    """
    inner_reject_outputs = [o for o in cfg.outputs if o.inner_join_reject]
    component_id = cfg.label or "tMap"

    lines: list[str] = [
        "import java.util.*;",
        "import com.citi.gru.etl.RowWrapper;",
        "",
    ]

    if not inner_reject_outputs:
        lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
        lines.append("return results;")
        return "\n".join(lines)

    # ---- Closures (one set per inner_join_reject output) ----
    per_output: list[tuple[OutputCfg, list[str]]] = []
    for out in inner_reject_outputs:
        out_defs, out_dispatch = _emit_output_section(
            out, cfg, component_id, is_reject_pass=True,
        )
        lines.extend(out_defs)
        per_output.append((out, out_dispatch))

    # ---- Buffer declarations ----
    for out in inner_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    lines.append("")

    # ---- Row loop (no try/catch, no Var, no filter) ----
    lines.append("for (int i = 0; i < rowCount; i++) {")
    lines.append(f'    RowWrapper {cfg.main.name} = buildRowWrapper(inputRoot, i, "{cfg.main.name}");')
    for lk in cfg.lookups:
        lines.append(f'    RowWrapper {lk.name} = buildRowWrapper(inputRoot, i, "{lk.name}");')
    lines.append("    Map<String, Object> Var = new HashMap<>();")  # empty Var for closure signature compatibility
    lines.append("")
    for out, dispatch_lines in per_output:
        ncols = len(out.columns)
        lines.append(f"    Object[] {out.name}_tempRow = new Object[{ncols}];")
        for d in dispatch_lines:
            lines.append(f"    {d}")
        lines.append(f"    {out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
    lines.append("}")
    lines.append("")

    # ---- Results map ----
    lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
    for out in inner_reject_outputs:
        lines.append(f"Map<String, Object> {out.name}_result = new HashMap<>();")
        lines.append(f'{out.name}_result.put("data", {out.name}_data);')
        lines.append(f'{out.name}_result.put("count", {out.name}_count);')
        lines.append(f'results.put("{out.name}", {out.name}_result);')
    lines.append("return results;")
    return "\n".join(lines)
```

- [ ] **Step 4: Run reject tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/map/test_map_compiled_script.py -v -k "build_reject_script"
```

Expected: all `build_reject_script` tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/map/map_compiled_script.py tests/v1/engine/components/transform/map/test_map_compiled_script.py
git commit -m "$(cat <<'EOF'
feat(tmap): rewrite build_reject_script with closure chunking

Symmetric with build_active_script. Reduced set of sections: no
variables, no filters, no is_reject routing, no try/catch. Empty
Var still passed for closure signature compatibility.

Spec section 4.7.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Run full unit-test suite to confirm no regressions outside tMap

**Files:** none (test-only verification)

- [ ] **Step 1: Run the full pure-Python test suite (no Java marker)**

```bash
python -m pytest tests/ -m "not java and not oracle" -n auto -q
```

Expected: same number of passes as before this plan, no new failures.

If any failure mentions `map_compiled_script` or asserts on the OLD inline shape, update the offending test to match the new closure-based shape (one-off edits — there should be none outside `test_map_compiled_script.py` and `test_map_compiled_script_chunking.py` which we've already updated).

- [ ] **Step 2: Commit (only if test fixes were needed)**

```bash
git add tests/
git commit -m "$(cat <<'EOF'
test(tmap): align stragglers with closure-based emitter shape

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

(Skip the commit step if no straggler updates were required.)

---

## Task 9: Live-bridge bullseye + pre-regression integration tests

**Files:**
- Modify: `tests/v1/engine/components/transform/test_map_method_too_large_integration.py` (append two integration tests; delete the two snapshot sanity tests from Task 1)

Now we prove (a) the new emitter compiles the 180-col fixture and (b) the legacy emitter genuinely fails on the same fixture.

- [ ] **Step 1: Delete the two snapshot sanity tests from Task 1**

In `tests/v1/engine/components/transform/test_map_method_too_large_integration.py`, delete these two function definitions:
- `test_legacy_snapshot_matches_current_active_emitter`
- `test_legacy_snapshot_matches_current_reject_emitter`

They've served their purpose — the legacy snapshot has been pinned and the live emitter has intentionally diverged.

- [ ] **Step 2: Write the failing bullseye + pre-regression tests**

Append to `tests/v1/engine/components/transform/test_map_method_too_large_integration.py`:

```python
# ===== Live-bridge integration tests =====

import pytest
import pandas as pd

from src.v1.engine.components.transform.map.map_compiled_script import (
    build_active_script,
)
from src.v1.engine.components.transform.map.map_config import parse_config


def _make_180_col_3000_char_config():
    """One output, 180 columns, each expression ~3000 chars.

    Source size: 180 * ~3050 = ~550KB -- well over the 64KB legacy limit,
    well under the per-expression 50KB hard cap.
    """
    # Each expression is row1.x + "<3000 chars of literal>" -- evaluates to
    # a string of the literal regardless of row1.x value (assuming row1.x
    # is null-coerce-friendly). Predictable expected output.
    pad = "P" * 2950  # the literal core
    cols = []
    for i in range(180):
        cols.append({
            "name": f"c{i}",
            "expression": f'(row1.id != null ? "" + row1.id : "") + "{pad}_{i}"',
            "type": "str",
        })
    raw = {
        "component_type": "Map",
        "label": "tMap_bullseye",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "out",
            "columns": cols,
            "is_reject": False, "inner_join_reject": False,
            "catch_output_reject": False, "filter": "", "activate_filter": False,
        }],
        "die_on_error": True,
    }
    return parse_config(raw)


@pytest.mark.java
def test_bullseye_180col_3000char_compiles_and_runs_with_new_emitter(java_bridge):
    """The new closure-chunked emitter compiles and executes the 180x3000 case."""
    cfg = _make_180_col_3000_char_config()
    src = build_active_script(cfg)
    # Sanity: the new emitter does produce closure-based shape
    assert "def out_chunk0 =" in src

    # Compile via the bridge
    java_bridge.compile_tmap_script(
        component_id="tMap_bullseye",
        java_script=src,
        output_schemas={"out": [f"c{i}" for i in range(180)]},
        output_types={f"out_c{i}": "str" for i in range(180)},
        main_table_name="row1",
        lookup_names=[],
    )

    # Run on 10 rows
    df = pd.DataFrame({"id": list(range(10))})
    result = java_bridge.execute_compiled_tmap_chunked(
        component_id="tMap_bullseye",
        df=df,
        chunk_size=50,
        input_columns=["id"],
        schema={"row1": {"id": "int"}},
        reject_mode=False,
    )
    out_df = result["out"]
    assert len(out_df) == 10
    assert len(out_df.columns) == 180
    # Spot-check row 3, column c42
    expected = "3" + ("P" * 2950) + "_42"
    assert out_df.iloc[3]["c42"] == expected


@pytest.mark.java
def test_pre_regression_legacy_emitter_fails_on_180col_3000char(java_bridge):
    """The legacy emitter genuinely throws MethodTooLargeException on
    this fixture, proving the failure mode is real (not a false positive
    where our test fixture was too small to trigger the original bug).
    """
    from py4j.protocol import Py4JJavaError

    cfg = _make_180_col_3000_char_config()
    legacy_src = _legacy_build_active_script(cfg)

    with pytest.raises(Py4JJavaError) as exc:
        java_bridge.compile_tmap_script(
            component_id="tMap_bullseye_legacy",
            java_script=legacy_src,
            output_schemas={"out": [f"c{i}" for i in range(180)]},
            output_types={f"out_c{i}": "str" for i in range(180)},
            main_table_name="row1",
            lookup_names=[],
        )

    # The inner Java exception class name appears in the stringified error
    err = str(exc.value)
    # Groovy wraps the ASM MethodTooLargeException in MultipleCompilationErrorsException
    assert (
        "MethodTooLarge" in err
        or "method too large" in err
        or "code too large" in err.lower()
    ), f"Expected method-too-large error, got: {err}"
```

(`java_bridge` is the existing fixture from `tests/conftest.py` or the project's java-bridge pytest fixture. If it's named differently in this repo, grep `@pytest.fixture` for the existing JavaBridge-providing fixture and use that name.)

- [ ] **Step 3: Run the two tests to verify they pass**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_method_too_large_integration.py -v -m java
```

Expected: 2 passed. Both tests must pass — if the bullseye fails the rewrite is wrong; if the pre-regression fails the fixture isn't big enough to trigger the legacy failure mode (in that case, increase `len(pad)` or column count until the legacy throws).

- [ ] **Step 4: Commit**

```bash
git add tests/v1/engine/components/transform/test_map_method_too_large_integration.py
git commit -m "$(cat <<'EOF'
test(tmap): live-bridge bullseye + pre-regression tests

Proves (a) the new closure-chunked emitter compiles and runs a
180-column / 3000-char-expression case end-to-end via the live
Java bridge, and (b) the pinned legacy emitter snapshot genuinely
throws MethodTooLargeException on the same fixture.

Closes the false-positive trap from the spec testing strategy
(section 9.2).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Live-bridge identicality tests on existing fixtures

**Files:**
- Modify: `tests/v1/engine/components/transform/test_map_method_too_large_integration.py` (append)

For each pre-existing tMap fixture JSON, run the same job through both the new emitter and the pinned legacy emitter. The output DataFrames must be byte-identical.

- [ ] **Step 1: Identify which fixtures to test**

```bash
ls tests/talend_xml_samples/converted_jsons/Job_tMap_*.json
```

Use every `Job_tMap_*.json` file present.

- [ ] **Step 2: Write the parameterized identicality test**

Append to `tests/v1/engine/components/transform/test_map_method_too_large_integration.py`:

```python
import json
import glob
import os

_FIXTURE_GLOB = "tests/talend_xml_samples/converted_jsons/Job_tMap_*.json"


def _load_tmap_configs_from_fixture(fixture_path: str) -> list[dict]:
    """Return all tMap-component configs from a fixture job JSON."""
    with open(fixture_path) as f:
        job = json.load(f)
    tmaps = []
    for comp in job.get("components", []):
        if comp.get("component_type") == "Map":
            tmaps.append(comp)
    return tmaps


@pytest.mark.java
@pytest.mark.parametrize("fixture_path", sorted(glob.glob(_FIXTURE_GLOB)))
def test_identicality_new_vs_legacy_emitter_on_fixture(java_bridge, fixture_path):
    """For every tMap component in every fixture JSON, the new emitter
    produces byte-identical output to the legacy emitter on a small
    synthetic input.
    """
    tmap_configs = _load_tmap_configs_from_fixture(fixture_path)
    if not tmap_configs:
        pytest.skip(f"No tMap component in {os.path.basename(fixture_path)}")

    for raw_cfg in tmap_configs:
        cfg = parse_config(raw_cfg)
        new_src = build_active_script(cfg)
        legacy_src = _legacy_build_active_script(cfg)

        # The scripts will differ in text, but their executed output
        # must match. Build synthetic inputs from the cfg's schema.
        synthetic = _build_synthetic_input_for_config(cfg, n_rows=5)
        if synthetic is None:
            pytest.skip(
                f"Could not build synthetic input for "
                f"{os.path.basename(fixture_path)} :: {cfg.label or '<unlabeled>'}"
            )

        # Compile + execute both, diff results
        # (Use distinct component_ids so caches don't collide.)
        java_bridge.compile_tmap_script(
            component_id=f"identicality_new_{cfg.label}",
            java_script=new_src,
            output_schemas={o.name: [c.name for c in o.columns]
                             for o in cfg.outputs if not o.inner_join_reject},
            output_types={f"{o.name}_{c.name}": c.type
                          for o in cfg.outputs if not o.inner_join_reject
                          for c in o.columns},
            main_table_name=cfg.main.name,
            lookup_names=[lk.name for lk in cfg.lookups],
        )
        java_bridge.compile_tmap_script(
            component_id=f"identicality_legacy_{cfg.label}",
            java_script=legacy_src,
            output_schemas={o.name: [c.name for c in o.columns]
                             for o in cfg.outputs if not o.inner_join_reject},
            output_types={f"{o.name}_{c.name}": c.type
                          for o in cfg.outputs if not o.inner_join_reject
                          for c in o.columns},
            main_table_name=cfg.main.name,
            lookup_names=[lk.name for lk in cfg.lookups],
        )

        new_result = java_bridge.execute_compiled_tmap_chunked(
            component_id=f"identicality_new_{cfg.label}",
            df=synthetic["df"], chunk_size=50,
            input_columns=synthetic["input_columns"],
            schema=synthetic["schema"], reject_mode=False,
        )
        legacy_result = java_bridge.execute_compiled_tmap_chunked(
            component_id=f"identicality_legacy_{cfg.label}",
            df=synthetic["df"], chunk_size=50,
            input_columns=synthetic["input_columns"],
            schema=synthetic["schema"], reject_mode=False,
        )

        # Compare each output DataFrame for byte-equality
        for out_name in new_result.keys():
            if out_name == "__errors__":
                continue
            new_df = new_result[out_name]
            legacy_df = legacy_result[out_name]
            pd.testing.assert_frame_equal(
                new_df.reset_index(drop=True),
                legacy_df.reset_index(drop=True),
                check_dtype=True, check_like=False,
                obj=f"output '{out_name}' of {cfg.label or fixture_path}",
            )


def _build_synthetic_input_for_config(cfg, n_rows: int) -> dict | None:
    """Build a minimal synthetic input DataFrame matching the cfg's main
    input. Returns None if we can't determine column types confidently
    (caller skips those configs).
    """
    # Pull main input column names from any output column or join key
    # that references row1.<col>. For real fixture coverage we rely on
    # the converter's input-schema block when present.
    main_name = cfg.main.name
    # Attempt: walk all expressions and join keys, extract `row1.X` patterns
    import re
    used_cols: set[str] = set()
    pat = re.compile(rf"\b{re.escape(main_name)}\.(\w+)")
    for o in cfg.outputs:
        for c in o.columns:
            for m in pat.findall(c.expression):
                used_cols.add(m)
        for m in pat.findall(o.filter):
            used_cols.add(m)
    for lk in cfg.lookups:
        for jk in lk.join_keys:
            for m in pat.findall(jk.expression):
                used_cols.add(m)

    if not used_cols:
        used_cols = {"id"}  # default minimal

    # All as int for simplicity. The identicality test isn't about
    # data correctness; it's about new-vs-legacy output equality.
    df = pd.DataFrame({col: list(range(n_rows)) for col in sorted(used_cols)})
    schema = {main_name: {col: "int" for col in sorted(used_cols)}}
    return {
        "df": df,
        "input_columns": sorted(used_cols),
        "schema": schema,
    }
```

- [ ] **Step 3: Run the identicality tests**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_method_too_large_integration.py -v -m java -k "identicality"
```

Expected: all parameterized tests PASS (or skip cleanly when synthetic input cannot be built for a fixture).

- [ ] **Step 4: Commit**

```bash
git add tests/v1/engine/components/transform/test_map_method_too_large_integration.py
git commit -m "$(cat <<'EOF'
test(tmap): identicality of new vs legacy emitter on existing fixtures

Parametrized over every Job_tMap_*.json fixture. Each tMap component
is compiled + executed via both the new closure-chunked emitter and
the pinned legacy emitter on a small synthetic input; output
DataFrames must be byte-identical via pd.testing.assert_frame_equal.

Spec section 9.2 (identicality test layer).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Edge case tests (single huge expression, NPE in 180-col, no-active-outputs)

**Files:**
- Modify: `tests/v1/engine/components/transform/test_map_method_too_large_integration.py` (append)

- [ ] **Step 1: Write the three edge case tests**

Append to `tests/v1/engine/components/transform/test_map_method_too_large_integration.py`:

```python
# ===== Edge cases =====

@pytest.mark.java
def test_edge_one_30kb_expression_gets_own_chunk_and_compiles(java_bridge):
    """Single column whose expression is 30KB compiles via own-chunk path."""
    huge_expr = '(row1.id != null ? "" + row1.id : "") + "' + ("X" * 29900) + '"'
    raw = {
        "component_type": "Map",
        "label": "tMap_one_huge",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "out",
            "columns": [
                {"name": "small", "expression": "row1.id", "type": "int"},
                {"name": "big", "expression": huge_expr, "type": "str"},
            ],
        }],
        "die_on_error": True,
    }
    cfg = parse_config(raw)
    src = build_active_script(cfg)
    java_bridge.compile_tmap_script(
        component_id="tMap_one_huge",
        java_script=src,
        output_schemas={"out": ["small", "big"]},
        output_types={"out_small": "int", "out_big": "str"},
        main_table_name="row1",
        lookup_names=[],
    )
    df = pd.DataFrame({"id": [7]})
    result = java_bridge.execute_compiled_tmap_chunked(
        component_id="tMap_one_huge",
        df=df, chunk_size=50,
        input_columns=["id"],
        schema={"row1": {"id": "int"}},
        reject_mode=False,
    )
    out = result["out"]
    assert len(out) == 1
    assert out.iloc[0]["small"] == 7
    assert out.iloc[0]["big"] == "7" + ("X" * 29900)


@pytest.mark.java
def test_edge_no_active_outputs_only_inner_join_reject(java_bridge):
    """Config with only inner_join_reject output -- active script produces
    empty results map; reject script produces populated output."""
    raw = {
        "component_type": "Map",
        "label": "tMap_only_reject",
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "rej", "inner_join_reject": True,
            "columns": [{"name": "id", "expression": "row1.id", "type": "int"}],
        }],
        "die_on_error": True,
    }
    cfg = parse_config(raw)
    # Active script must compile (even if it's essentially empty)
    active_src = build_active_script(cfg)
    java_bridge.compile_tmap_script(
        component_id="tMap_only_reject_active",
        java_script=active_src,
        output_schemas={},
        output_types={},
        main_table_name="row1",
        lookup_names=[],
    )
    # And reject script
    from src.v1.engine.components.transform.map.map_compiled_script import (
        build_reject_script,
    )
    reject_src = build_reject_script(cfg)
    java_bridge.compile_tmap_script(
        component_id="tMap_only_reject_reject",
        java_script=reject_src,
        output_schemas={"rej": ["id"]},
        output_types={"rej_id": "int"},
        main_table_name="row1",
        lookup_names=[],
    )


@pytest.mark.java
def test_edge_npe_in_one_row_routes_to_errors_with_closure_frame(java_bridge):
    """Row whose expression throws NPE is captured in __errors__ with
    rowIndex + errorMessage + errorStackTrace; the synthetic closure
    frame appears in the stack but the Python __errors__ parser
    handles it without modification.
    """
    raw = {
        "component_type": "Map",
        "label": "tMap_npe",
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "out",
            "columns": [
                # Force NPE when row1.id is null
                {"name": "val", "expression": "row1.id.intValue() + 1", "type": "int"},
            ],
            "catch_output_reject": False,
        }],
        "die_on_error": False,  # tolerate errors; route to __errors__
    }
    cfg = parse_config(raw)
    src = build_active_script(cfg)
    java_bridge.compile_tmap_script(
        component_id="tMap_npe",
        java_script=src,
        output_schemas={"out": ["val"]},
        output_types={"out_val": "int"},
        main_table_name="row1",
        lookup_names=[],
    )
    # Row 1 has null id -> NPE
    df = pd.DataFrame({"id": [1, None, 3]}).astype({"id": "Int64"})
    result = java_bridge.execute_compiled_tmap_chunked(
        component_id="tMap_npe",
        df=df, chunk_size=50,
        input_columns=["id"],
        schema={"row1": {"id": "int"}},
        reject_mode=False,
    )
    errs = result.get("__errors__")
    assert errs is not None
    assert not errs.empty
    npe_row = errs[errs["rowIndex"] == 1].iloc[0]
    assert "NullPointer" in npe_row["errorMessage"] or "null" in npe_row["errorMessage"].lower()
    # Closure frame appears in the stack trace; Python parser still produced
    # a well-formed DataFrame row, which is what matters.
    assert "$_run_closure" in npe_row["errorStackTrace"] or "doCall" in npe_row["errorStackTrace"]
```

- [ ] **Step 2: Run the edge-case tests**

```bash
python -m pytest tests/v1/engine/components/transform/test_map_method_too_large_integration.py -v -m java -k "edge_"
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/v1/engine/components/transform/test_map_method_too_large_integration.py
git commit -m "$(cat <<'EOF'
test(tmap): edge cases for closure-chunked emitter

(a) One 30KB expression in its own chunk compiles + executes.
(b) Config with only inner_join_reject output -- both scripts compile.
(c) NPE row routes to __errors__ with closure frame visible in stack;
    Python __errors__ parser handles the synthetic frame transparently.

Spec section 9.3.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Final coverage gate + full-suite regression

**Files:** none (test-only verification)

- [ ] **Step 1: Run the coverage gate command from CLAUDE.md**

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected outcome (from CLAUDE.md):
- Exit 0 with final stdout line `PASS: all 181 in-scope modules at >= 95.0% line coverage`
- `htmlcov/index.html` regenerated
- `coverage.json` regenerated

If `map_compiled_script.py` drops below 95%, add coverage by:
1. Identifying the uncovered branches via `coverage.json` or the term-missing report.
2. Adding unit tests in `tests/v1/engine/components/transform/map/test_map_compiled_script_chunking.py` to cover them.

- [ ] **Step 2: Confirm working tree is clean and on the right branch**

```bash
git status
git branch --show-current
```

Expected: working tree clean; branch `feature/engine-restructure`.

- [ ] **Step 3: Spot-check the commits on this branch**

```bash
git log --oneline main..HEAD
```

Expected: commits for Tasks 1, 2, 3, 4, 5, 6, 7, (optionally 8), 9, 10, 11 -- one commit per task, clear feat/test/docs prefixes.

---

## Final verification (after Task 12)

The manager's failing case is now provably fixed:
- Bullseye test (Task 9) demonstrates a 180-col / 3000-char fixture compiles and runs.
- Pre-regression test (Task 9) demonstrates the legacy emitter would have failed on the same fixture.
- Identicality tests (Task 10) demonstrate no behavior change for existing jobs.
- Edge cases (Task 11) cover huge single expressions, degenerate configs, and `__errors__` routing.
- Coverage gate (Task 12) confirms 95% per-module floor preserved.
