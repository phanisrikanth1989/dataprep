"""Groovy script generation for tMap compiled execution.

Pure functions: takes parsed MapConfig in, returns a Groovy source string.
No bridge calls, no state. See spec section 7.

Two entry points (added in subsequent tasks):
- build_active_script(cfg) -> active-pass script (vars + outputs + is_reject +
  catch_output_reject error capture).
- build_reject_script(cfg) -> reject-pass script (inner_join_reject column
  expressions only).

This module is built incrementally:
- Task 3.1: groovy_escape_expression (helper)
- Task 3.2+3.3: build_active_script
- Task 3.4: build_reject_script
"""
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


def groovy_escape_expression(java_expr: str) -> str:
    """Escape ``$`` inside double-quoted string literals.

    Groovy GString interpolates ``$identifier`` / ``${expr}`` at runtime.
    Talend Java expressions like ``"Total: $100"`` would either parse-error
    or, worse, evaluate an unintended identifier. Outside string literals,
    ``$`` is a legal identifier character in both Java and Groovy -- left
    alone.

    Escape sequences (``\\\\``, ``\\"``) inside a string region are consumed
    as two-character units so they cannot mis-detect the closing quote.

    Single-quoted strings (Groovy char literals) are treated as
    outside-string regions; ``$`` inside them is not interpolated by Groovy
    anyway.

    Args:
        java_expr: Java/Groovy expression text (already stripped of any
            ``{{java}}`` marker by the caller).

    Returns:
        Expression with ``$`` inside double-quoted strings escaped to ``\\$``.
    """
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
        # Inside a double-quoted string literal
        if ch == "\\" and i + 1 < n:
            # Two-char escape (e.g. \" or \\); consume both
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


def _strip_marker(expr: str) -> str:
    """Remove the ``{{java}}`` prefix if present."""
    return expr[len("{{java}}"):] if expr.startswith("{{java}}") else expr


def build_active_script(cfg: MapConfig) -> str:
    """Build the active-pass Groovy script for a tMap.

    Covers: row wrapper construction, variables, all active (non-reject)
    output columns with filter routing, is_reject routing, and (when any
    catch_output_reject output exists OR die_on_error=False) try/catch
    with errorMap/stackTraceMap.

    Variables are emitted as a HashMap<String, Object> Var. Sequential
    chaining works because later vars use Var.get("earlier") which reads
    the just-populated entry.

    The script binds buildRowWrapper, inputRoot, rowCount, context,
    globalMap on the Java side (see JavaBridge.buildTMapBinding).

    See spec section 7 for the full shape.

    Args:
        cfg: Parsed MapConfig.

    Returns:
        Groovy source string ready for compilation.
    """
    lines: list[str] = []

    # Imports
    lines.append("import java.util.*;")
    lines.append("import com.citi.gru.etl.RowWrapper;")
    lines.append("")

    # Output classification
    active_outputs = [
        o for o in cfg.outputs
        if not o.is_reject and not o.inner_join_reject and not o.catch_output_reject
    ]
    is_reject_outputs = [o for o in cfg.outputs if o.is_reject]
    catch_outputs = [o for o in cfg.outputs if o.catch_output_reject]

    has_error_tracking = (not cfg.die_on_error) or bool(catch_outputs)

    # Buffer declarations
    for out in active_outputs + is_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    if has_error_tracking:
        lines.append("int errorCount = 0;")
        lines.append("Map<Integer, String> errorMap = new HashMap<>();")
        lines.append("Map<Integer, String> stackTraceMap = new HashMap<>();")
    lines.append("")

    # Row loop
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

    # Variables map (always emitted)
    lines.append(f"{body_indent}Map<String, Object> Var = new HashMap<>();")
    for v in cfg.variables:
        expr = groovy_escape_expression(_strip_marker(v.expression)) or "null"
        lines.append(f'{body_indent}Var.put("{v.name}", {expr});')
    lines.append("")

    # Track is_reject routing
    if is_reject_outputs:
        lines.append(f"{body_indent}boolean matchedAny = false;")

    # Active outputs -- atomic-row commit
    for out in active_outputs:
        ncols = len(out.columns)
        lines.append(f"{body_indent}// Active output: {out.name}")
        if out.activate_filter and out.filter:
            filter_expr = groovy_escape_expression(_strip_marker(out.filter))
            lines.append(f"{body_indent}if ({filter_expr}) {{")
        else:
            lines.append(f"{body_indent}{{")
        inner = body_indent + "    "
        lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
        for j, col in enumerate(out.columns):
            expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
            lines.append(f"{inner}{out.name}_tempRow[{j}] = {expr};")
        if is_reject_outputs:
            lines.append(f"{inner}matchedAny = true;")
        lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")
    lines.append("")

    # is_reject routing
    if is_reject_outputs:
        lines.append(f"{body_indent}if (!matchedAny) {{")
        for out in is_reject_outputs:
            ncols = len(out.columns)
            inner = body_indent + "    "
            lines.append(f"{inner}Object[] {out.name}_tempRow = new Object[{ncols}];")
            for j, col in enumerate(out.columns):
                expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
                lines.append(f"{inner}{out.name}_tempRow[{j}] = {expr};")
            lines.append(f"{inner}{out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
        lines.append(f"{body_indent}}}")

    # Inner try/catch for error tracking
    if has_error_tracking:
        lines.append("        } catch (Exception innerE) {")
        lines.append("            String msg = innerE.getMessage() != null ? innerE.getMessage() : innerE.toString();")
        lines.append("            java.io.StringWriter sw = new java.io.StringWriter();")
        lines.append("            innerE.printStackTrace(new java.io.PrintWriter(sw));")
        lines.append("            errorCount++;")
        lines.append("            errorMap.put(i, msg);")
        lines.append("            stackTraceMap.put(i, sw.toString());")
        lines.append("        }")

    # Outer try (row wrapper construction errors): always re-raise
    lines.append("    } catch (Exception outerE) {")
    lines.append("        String msg = outerE.getMessage() != null ? outerE.getMessage() : outerE.toString();")
    lines.append('        throw new RuntimeException("Error at row " + i + ": " + msg, outerE);')
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # Results map
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


def build_reject_script(cfg: MapConfig) -> str:
    """Build the reject-pass Groovy script for inner_join_reject outputs.

    Strictly smaller than the active script:
    - No variables (reject rows have no Var state)
    - No filters (every reject row routes to every inner_join_reject output)
    - No try/catch / errorMap (any error during reject column eval propagates;
      we already lost the join, no further reject routing)
    - One row loop, one results map

    When no output has inner_join_reject=True, returns a trivial
    empty-results script.

    Args:
        cfg: Parsed MapConfig.

    Returns:
        Groovy source string. Used by Map._process to compile and execute
        a second bridge pass over the reject row source (only when
        inner_join_reject_dfs from the join phase is non-empty).
    """
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

    # Output buffers
    for out in inner_reject_outputs:
        ncols = len(out.columns)
        lines.append(f"Object[][] {out.name}_data = new Object[rowCount][{ncols}];")
        lines.append(f"int {out.name}_count = 0;")
    lines.append("")

    # Row loop -- no try/catch, no variables, no filter
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
            expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
            lines.append(f"    {out.name}_tempRow[{j}] = {expr};")
        lines.append(f"    {out.name}_data[{out.name}_count++] = {out.name}_tempRow;")
    lines.append("}")
    lines.append("")

    # Results map
    lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
    for out in inner_reject_outputs:
        lines.append(f"Map<String, Object> {out.name}_result = new HashMap<>();")
        lines.append(f'{out.name}_result.put("data", {out.name}_data);')
        lines.append(f'{out.name}_result.put("count", {out.name}_count);')
        lines.append(f'results.put("{out.name}", {out.name}_result);')
    lines.append("return results;")
    return "\n".join(lines)
