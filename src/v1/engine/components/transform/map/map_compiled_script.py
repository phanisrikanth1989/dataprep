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

from .map_config import MapConfig, OutputCfg
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


def _emit_closure_chunks(
    emitted_lines: list[str],
    per_line_labels: list[str],
    *,
    component_id: str,
    chunk_name_prefix: str,
    closure_param_sig: str,
    closure_call_args: str,
) -> tuple[list[str], list[str]]:
    """Shared helper: pre-scan lines for hard-cap, chunk, then emit closures.

    Pre-scans ``emitted_lines`` per-line for hard-cap violations (using the
    parallel ``per_line_labels`` to name the offending item in the error),
    then chunks via ``_chunk_emitted_lines``, then emits numbered closures
    using the supplied signature, name prefix, and dispatch call args.

    Args:
        emitted_lines: full list of Groovy statement strings to emit.
        per_line_labels: parallel list of human-readable labels for each line,
            used only in hard-cap ``ConfigurationError`` messages.
        component_id: tMap component id for error messages.
        chunk_name_prefix: closure name prefix, e.g. ``"vars_chunk"``,
            ``"out1_chunk"``, ``"out1_reject_chunk"``.
        closure_param_sig: Groovy parameter signature string to place inside
            ``{ <sig> -> ... }``, e.g.
            ``"int i, RowWrapper row1, Map Var"``.
        closure_call_args: argument list for the ``.call(...)`` dispatch site,
            e.g. ``"i, row1, Var"``.

    Returns:
        (closure_defs, dispatch_lines): lists of source lines ready to
        ``extend`` onto the script's line buffer.

    Raises:
        ConfigurationError: if any single line exceeds ``_SINGLE_EXPR_HARD_CAP``.
    """
    # Pre-scan with per-item labels for actionable error messages
    for line, label in zip(emitted_lines, per_line_labels):
        if len(line) > _SINGLE_EXPR_HARD_CAP:
            raise ConfigurationError(
                f"tMap component '{component_id}': {label} expression "
                f"is {len(line)} chars, exceeds the {_SINGLE_EXPR_HARD_CAP}-char limit. "
                f"Split the expression into a Var or reduce its size."
            )

    # Chunk (the hard-cap path inside _chunk_emitted_lines is now unreachable)
    chunks = _chunk_emitted_lines(
        emitted_lines,
        section_label=chunk_name_prefix,
        component_id=component_id,
    )

    closure_defs: list[str] = []
    dispatch_lines: list[str] = []
    for idx, chunk in enumerate(chunks):
        closure_name = f"{chunk_name_prefix}{idx}"
        closure_defs.append(f"def {closure_name} = {{ {closure_param_sig} ->")
        for line in chunk:
            closure_defs.append(f"    {line}")
        closure_defs.append("};")
        closure_defs.append("")
        dispatch_lines.append(f"{closure_name}.call({closure_call_args});")

    return closure_defs, dispatch_lines


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

    # Build the per-variable emitted lines + labels
    var_lines: list[str] = []
    var_labels: list[str] = []
    for v in cfg.variables:
        expr = groovy_escape_expression(_strip_marker(v.expression)) or "null"
        var_lines.append(f'Var.put("{v.name}", {expr});')
        var_labels.append(f"variable '{v.name}'")

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

    return _emit_closure_chunks(
        var_lines,
        var_labels,
        component_id=component_id,
        chunk_name_prefix="vars_chunk",
        closure_param_sig=sig,
        closure_call_args=call_args,
    )


def _emit_output_section(
    out: OutputCfg,
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
    # Build per-column emitted lines + labels
    col_lines: list[str] = []
    col_labels: list[str] = []
    for j, col in enumerate(out.columns):
        expr = groovy_escape_expression(_strip_marker(col.expression)) or "null"
        col_lines.append(f"tempRow[{j}] = {expr};")
        col_labels.append(f"output '{out.name}' column '{col.name}'")

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

    return _emit_closure_chunks(
        col_lines,
        col_labels,
        component_id=component_id,
        chunk_name_prefix=f"{out.name}_{suffix}",
        closure_param_sig=sig,
        closure_call_args=call_args,
    )


def _emit_filter_section(
    out: OutputCfg,
    cfg: MapConfig,
    component_id: str,
) -> tuple[str | None, str]:
    """Build the filter for one output: inline expression or hoisted closure.

    Filters under ``_CHUNK_TARGET_CHARS`` stay inline in the row loop's
    ``if (...)`` guard. Filters above that threshold are hoisted to a
    single-expression closure (``{out.name}_filter``) defined alongside
    the other closures at the top of ``run()``.

    Args:
        out: OutputCfg whose filter to emit.
        cfg: full MapConfig (used for main + lookup names in closure signature).
        component_id: tMap component id for error messages.

    Returns:
        (closure_def_or_None, callable_expression)
        closure_def_or_None: full closure source string if the filter was
            hoisted, else None.
        callable_expression: the Groovy expression for the row loop's
            ``if (...)`` -- either the raw filter or a closure call like
            ``out1_filter.call(i, row1, lkp1, Var)``.

    Raises:
        ConfigurationError: if the emitted filter exceeds ``_SINGLE_EXPR_HARD_CAP``.
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

    active_per_output: list[tuple[OutputCfg, str, list[str]]] = []
    # Each tuple: (out, filter_callable_expr, output_dispatch_lines)
    for out in active_outputs:
        filter_closure_def, filter_expr = _emit_filter_section(out, cfg, component_id)
        if filter_closure_def:
            lines.append(filter_closure_def.rstrip())
            lines.append("")
        out_defs, out_dispatch = _emit_output_section(
            out, cfg, component_id, is_reject_pass=False,
        )
        lines.extend(out_defs)
        active_per_output.append((out, filter_expr, out_dispatch))

    # is_reject outputs in the active script still use the regular _chunk naming;
    # _reject_chunk is reserved for inner_join_reject outputs in build_reject_script.
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
    for out, filter_expr, dispatch_lines in active_per_output:
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
