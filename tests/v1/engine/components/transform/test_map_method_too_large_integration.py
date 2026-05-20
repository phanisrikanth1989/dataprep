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
