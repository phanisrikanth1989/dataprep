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


# ===== Live-bridge integration tests =====

import pytest
import pandas as pd

from src.v1.engine.components.transform.map.map_compiled_script import (
    build_active_script,
)
from src.v1.engine.components.transform.map.map_config import parse_config


def _make_400_col_ternary_config():
    """One output, 400 columns, each a ternary/String.valueOf expression.

    These expressions generate real JVM bytecode (not just constant-pool
    string literals), so the legacy monolithic run() method crosses the
    64KB bytecode limit at 400 columns.  The new closure-chunked emitter
    splits the column assignments across multiple closures so each closure
    stays well under the limit.

    Only requires a single input column ('id') on row1.
    Expected output for row N, column c{i}: "<N>_c{i}".
    """
    cols = []
    for i in range(400):
        # Realistic ternary: generates a ternary + String.valueOf + concat
        # in bytecode -- enough instructions per column to hit 64KB at 400 cols.
        cols.append({
            "name": f"c{i}",
            "expression": f'(row1.id != null ? String.valueOf(row1.id) + "_c{i}" : "null_c{i}")',
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
def test_bullseye_400col_ternary_compiles_and_runs_with_new_emitter(java_bridge):
    """The new closure-chunked emitter compiles and executes the 400-col ternary case."""
    cfg = _make_400_col_ternary_config()
    src = build_active_script(cfg)
    # Sanity: the new emitter produces closure-based shape
    assert "def out_chunk0 =" in src

    # Compile via the bridge
    java_bridge.compile_tmap_script(
        component_id="tMap_bullseye",
        java_script=src,
        output_schemas={"out": [f"c{i}" for i in range(400)]},
        output_types={f"out_c{i}": "str" for i in range(400)},
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
        schema={"id": "int"},
        reject_mode=False,
    )
    out_df = result["out"]
    assert len(out_df) == 10
    assert len(out_df.columns) == 400
    # Spot-check row 3, column c42: id=3 -> "3_c42"
    assert out_df.iloc[3]["c42"] == "3_c42"


@pytest.mark.java
def test_pre_regression_legacy_emitter_fails_on_400col_ternary(java_bridge):
    """The legacy emitter genuinely throws MethodTooLargeException on the
    400-col ternary fixture, proving the failure mode is real (not a
    false positive where the test fixture was too small to trigger it).

    Note: the 400-col ternary expressions generate enough JVM bytecode
    instructions in the monolithic run() method to exceed the 64KB limit.
    Large string literals alone do not trigger the limit because they are
    stored in the constant pool, not as method instructions.
    """
    from py4j.protocol import Py4JJavaError

    cfg = _make_400_col_ternary_config()
    legacy_src = _legacy_build_active_script(cfg)

    with pytest.raises(Py4JJavaError) as exc:
        java_bridge.compile_tmap_script(
            component_id="tMap_bullseye_legacy",
            java_script=legacy_src,
            output_schemas={"out": [f"c{i}" for i in range(400)]},
            output_types={f"out_c{i}": "str" for i in range(400)},
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
