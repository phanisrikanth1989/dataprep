"""Live-bridge integration tests for tMap MethodTooLarge fix.

Holds a frozen snapshot of the legacy emitter (`_legacy_build_active_script`,
`_legacy_build_reject_script`, helpers) so the pre-regression test in this
file can prove the failure mode is real without depending on git history.

Tests in this file require a running Java bridge: `@pytest.mark.java`.
"""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

import pandas as pd
import pytest

from src.v1.engine.components.transform.map.map_compiled_script import (
    build_active_script,
)
from src.v1.engine.components.transform.map.map_config import MapConfig, parse_config


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


def _make_400_col_ternary_config():
    """One output, 400 columns, each expression a ternary on row1.id.

    The plan originally called for 180 cols x ~3000-char pad-string
    expressions, but large string LITERALS go to the JVM constant pool
    and contribute almost nothing to method bytecode (just an ldc
    instruction). To genuinely exercise the 64KB per-method bytecode
    limit, we need expressions that emit real opcodes (ALOAD,
    INVOKESTATIC, StringBuilder.append, branch instructions, etc.).

    400 ternary expressions of the form
        (row1.id != null ? String.valueOf(row1.id) + "_c{N}" : "null_c{N}")
    each generate ~40-60 bytes of bytecode, pushing the legacy monolithic
    run() method past 64KB and triggering MethodTooLargeException.

    Source size: 400 * ~70 chars = ~28KB -- under the per-expression
    50KB hard cap. Output values are predictable: row.id=K column c{N}
    produces "K_cN" so the bullseye test can verify correctness across
    every chunk boundary.
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
    # Verify cells across the full column range so every chunk closure is
    # exercised. The 400 columns split into multiple chunks (per
    # _CHUNK_TARGET_CHARS); sampling every ~40 columns guarantees we hit
    # every chunk and catches closure-capture bugs that would only affect
    # later chunks.
    sample_cols = list(range(0, 400, 40)) + [399]  # 0, 40, 80, ..., 360, 399 (11 cols)
    sample_rows = [0, 3, 9]  # first, middle, last
    for row_idx in sample_rows:
        for col_idx in sample_cols:
            actual = out_df.iloc[row_idx][f"c{col_idx}"]
            expected = f"{row_idx}_c{col_idx}"
            assert actual == expected, (
                f"row {row_idx} col c{col_idx}: expected {expected!r}, got {actual!r}"
            )


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


# ===== Identicality tests: new emitter vs legacy emitter on existing fixtures =====

# Anchor to repo root so pytest can run from any cwd without silently
# producing zero parametrize cases.
_FIXTURES_DIR = Path(__file__).resolve().parents[5] / "tests" / "talend_xml_samples" / "converted_jsons"
_FIXTURE_GLOB = str(_FIXTURES_DIR / "Job_tMap_*.json")

_FIXTURE_PATHS = sorted(glob.glob(_FIXTURE_GLOB))
assert _FIXTURE_PATHS, (
    f"No tMap fixtures discovered at {_FIXTURE_GLOB} -- "
    f"pytest collection failure"
)


def _load_tmap_configs_from_fixture(fixture_path: str) -> list[dict]:
    """Return all tMap config dicts (ready for parse_config) from a fixture job JSON.

    The fixture format wraps the engine config under a ``config`` sub-key and uses
    ``type`` (not ``component_type``) to identify component kind.  We extract the
    inner config block and inject ``label`` from the component ``id`` when absent.
    """
    with open(fixture_path) as f:
        job = json.load(f)
    tmaps = []
    for comp in job.get("components", []):
        if comp.get("type") == "Map":
            cfg_block = dict(comp.get("config") or {})
            # Inject label from the component id if the config block lacks one
            if not cfg_block.get("label"):
                cfg_block["label"] = comp.get("id", "tMap_unknown")
            tmaps.append(cfg_block)
    return tmaps


def _build_synthetic_input_for_config(cfg, n_rows: int) -> dict | None:
    """Build a minimal synthetic input DataFrame matching the cfg's main
    AND lookup inputs.

    Walks output column expressions, output filters, and lookup join-key
    expressions for `<table>.<col>` references where `<table>` is either
    the main input name or any lookup name. Synthesizes int columns for
    each (table, col) pair so the Java bridge has all referenced fields
    available -- otherwise identicality holds trivially via null == null
    on every lookup column.

    Returns None if no referenced columns can be inferred (caller skips
    that config).
    """
    table_names = [cfg.main.name] + [lk.name for lk in cfg.lookups]
    # Match `table.col` for any of our known tables
    pattern_parts = "|".join(re.escape(t) for t in table_names)
    pat = re.compile(rf"\b({pattern_parts})\.(\w+)")

    refs: set[tuple[str, str]] = set()
    for o in cfg.outputs:
        for c in o.columns:
            for table, col in pat.findall(c.expression):
                refs.add((table, col))
        for table, col in pat.findall(o.filter):
            refs.add((table, col))
    for lk in cfg.lookups:
        for jk in lk.join_keys:
            for table, col in pat.findall(jk.expression):
                refs.add((table, col))

    if not refs:
        return None

    # Group columns by table
    by_table: dict[str, set[str]] = {}
    for table, col in refs:
        by_table.setdefault(table, set()).add(col)

    # Flat schema for the bridge (each lookup row has its own columns).
    # The bridge's joined DataFrame for tMap puts all columns into a single
    # Arrow root. Use flat naming where the main table's columns are at the
    # root, and lookup-table columns share the root too (the bridge handles
    # this via RowWrapper's table-prefix lookup logic).
    cols_in_order = sorted({c for cols in by_table.values() for c in cols})

    # All ints for simplicity -- identicality is about emitter equality, not
    # type coercion correctness.
    df = pd.DataFrame({col: list(range(n_rows)) for col in cols_in_order})
    schema = {col: "int" for col in cols_in_order}
    return {
        "df": df,
        "input_columns": cols_in_order,
        "schema": schema,
    }


@pytest.mark.java
@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS)
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

        # Compile + execute both, diff results.
        # Scope component_ids to the fixture file so cache entries from
        # different fixture files with identically-labeled tMap components
        # cannot collide.
        _fixture_key = os.path.splitext(os.path.basename(fixture_path))[0]
        new_cid = f"identicality_new_{_fixture_key}_{cfg.label}"
        legacy_cid = f"identicality_legacy_{_fixture_key}_{cfg.label}"

        java_bridge.compile_tmap_script(
            component_id=new_cid,
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
            component_id=legacy_cid,
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
            component_id=new_cid,
            df=synthetic["df"], chunk_size=50,
            input_columns=synthetic["input_columns"],
            schema=synthetic["schema"], reject_mode=False,
        )
        legacy_result = java_bridge.execute_compiled_tmap_chunked(
            component_id=legacy_cid,
            df=synthetic["df"], chunk_size=50,
            input_columns=synthetic["input_columns"],
            schema=synthetic["schema"], reject_mode=False,
        )

        # Catch the case where one emitter produces an output the other doesn't.
        new_keys = set(new_result.keys()) - {"__errors__"}
        legacy_keys = set(legacy_result.keys()) - {"__errors__"}
        assert new_keys == legacy_keys, (
            f"Emitters produced different output sets for "
            f"{os.path.basename(fixture_path)} :: {cfg.label}: "
            f"new={new_keys}, legacy={legacy_keys}"
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
