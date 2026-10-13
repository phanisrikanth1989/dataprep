# tests/agents/tools/test_surface_code_cells.py
"""Deterministic surfacing of code-bearing config cells for the human gate (I-2)."""
import json

from agents.tools.surface_code_cells import main, surface_code_cells


# ---- core extractor -------------------------------------------------------

def test_surfaces_python_dataframe_as_unsandboxed():
    job = {"components": [
        {"id": "pdf", "type": "PythonDataFrameComponent", "config": {"python_code": "df['x']=1"}},
        {"id": "py", "type": "tPython", "config": {"python_code": "pass"}},
        {"id": "conv", "type": "ConvertType", "config": {"autocast": True}},
    ]}
    cells = surface_code_cells(job)
    by = {c["component"]: c for c in cells}
    assert by["pdf"]["unsandboxed"] is True and by["pdf"]["code"] == "df['x']=1"
    assert by["py"]["unsandboxed"] is False
    assert "conv" not in by            # no code cell
    assert cells[0]["unsandboxed"] is True   # unsandboxed surfaced first


def test_surfaces_java_marker_tmap_expression():
    job = {"components": [{"id": "m", "type": "Map", "config": {"outputs": [
        {"name": "out", "columns": [{"name": "c", "expression": "{{java}}row1.amt * 2"}]}]}}]}
    cells = surface_code_cells(job)
    assert any(c["component"] == "m" and "{{java}}" in c["code"] for c in cells)


def test_cli(tmp_path, capsys):
    p = tmp_path / "job.json"
    p.write_text(json.dumps({"components": [
        {"id": "pdf", "type": "tPythonDataFrame", "config": {"python_code": "df"}}]}))
    rc = main(["--job", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out[0]["unsandboxed"] is True


# ---- java components ------------------------------------------------------

def test_java_components_surface_code_keys():
    job = {"components": [
        {"id": "j", "type": "tJava", "config": {"java_code": "System.out.println(1);"}},
        {"id": "jr", "type": "tJavaRow", "config": {"java_code": "output_row.x = input_row.x;"}},
        {"id": "jf", "type": "JavaFlex", "config": {
            "code_start": "int i=0;", "code_main": "i++;", "code_end": "return i;"}},
    ]}
    cells = surface_code_cells(job)
    by_field = {(c["component"], c["field"]): c for c in cells}
    assert by_field[("j", "java_code")]["unsandboxed"] is False
    assert by_field[("jr", "java_code")]["code"] == "output_row.x = input_row.x;"
    # all three JavaFlex code segments surfaced verbatim
    assert {("jf", "code_start"), ("jf", "code_main"), ("jf", "code_end")} <= set(by_field)
    assert by_field[("jf", "code_main")]["code"] == "i++;"


def test_python_row_is_sandboxed():
    job = {"components": [
        {"id": "pr", "type": "tPythonRow", "config": {"python_code": "output = input"}}]}
    cells = surface_code_cells(job)
    assert cells[0]["component"] == "pr" and cells[0]["unsandboxed"] is False


# ---- PyMap + SwiftTransformer (I-4) ---------------------------------------

def test_surfaces_pymap_expressions():
    job = {"components": [{"id": "pm", "type": "PyMap", "config": {
        "variables": [{"name": "v", "expression": "row1.amt * 2"}],
        "outputs": [{"name": "o", "filter": "row1.amt > 0",
                     "columns": [{"name": "c", "expression": "row1.amt + var.v"}]}]}}]}
    cells = surface_code_cells(job)
    codes = [c["code"] for c in cells if c["component"] == "pm"]
    assert any("row1.amt * 2" in c for c in codes)      # variable expression
    assert any("row1.amt + var.v" in c for c in codes)  # output column expression
    assert any("row1.amt > 0" in c for c in codes)      # output filter
    assert all(c["unsandboxed"] is False for c in cells if c["component"] == "pm")


def test_surfaces_pymap_input_and_lookup_expressions():
    # main filter, lookup filter, and lookup join-key expressions are surfaced too.
    job = {"components": [{"id": "pm", "type": "PyMap", "config": {
        "inputs": {
            "main": {"name": "row1", "filter": "row1.qty > 0"},
            "lookups": [{"name": "row2", "filter": "row2.active == 1",
                         "join_keys": [{"lookup_column": "id",
                                        "expression": "row1.cust_id"}]}],
        },
        "outputs": [{"name": "o", "columns": [{"name": "c", "expression": "row1.qty"}]}]}}]}
    fields = {c["field"]: c["code"] for c in surface_code_cells(job)
              if c["component"] == "pm"}
    assert fields["inputs.main.filter"] == "row1.qty > 0"
    assert fields["inputs.lookups[0].filter"] == "row2.active == 1"
    assert fields["inputs.lookups[0].join_keys[0].expression"] == "row1.cust_id"


def test_pymap_blank_expressions_not_surfaced():
    job = {"components": [{"id": "pm", "type": "PyMap", "config": {
        "variables": [{"name": "v", "expression": "   "}],
        "outputs": [{"name": "o", "filter": "",
                     "columns": [{"name": "c", "expression": "row1.amt"}]}]}}]}
    fields = {c["field"] for c in surface_code_cells(job) if c["component"] == "pm"}
    assert fields == {"outputs[0].columns[0].expression"}


def test_surfaces_swift_python_expression_as_unsandboxed():
    job = {"components": [{"id": "sw", "type": "tSwiftDataTransformer",
        "config": {"transform_config": {"mapping": [{"python_expression": "__import__('os').getcwd()"}]}}}]}
    cells = surface_code_cells(job)
    sw = [c for c in cells if c["component"] == "sw"]
    assert sw and sw[0]["unsandboxed"] is True and "__import__" in sw[0]["code"]


def test_surfaces_swift_alias_and_nested_python_expressions():
    # The camelCase alias works, and every nested python_expression is surfaced.
    job = {"components": [{"id": "sw", "type": "SwiftTransformer", "config": {
        "transform_config": {"output_fields": [
            {"name": "A", "python_expression": "input_row['x']"},
            {"name": "B", "python_expression": "computed['A'] + '1'"},
            {"name": "C", "python_expression": "   "},  # blank -> skipped
        ]}}}]}
    codes = [c["code"] for c in surface_code_cells(job) if c["component"] == "sw"]
    assert "input_row['x']" in codes
    assert "computed['A'] + '1'" in codes
    assert "   " not in codes and len(codes) == 2
    assert all(c["unsandboxed"] is True
               for c in surface_code_cells(job) if c["component"] == "sw")


def test_surfaces_swift_external_config_file_as_unsurfaced_cell():
    # An EXTERNAL config_file loads python_expression fields this walker cannot
    # read -> it MUST be flagged as an unsurfaced (unsandboxed) cell so the gate is
    # never silently blind to the code the job will eval (C1).
    job = {"components": [{"id": "sw", "type": "tSwiftDataTransformer",
        "config": {"config_file": "/mnt/cfg/swift_map.yaml", "output_file": "out.pipe"}}]}
    cells = surface_code_cells(job)
    sw = [c for c in cells if c["component"] == "sw"]
    assert len(sw) == 1
    cell = sw[0]
    assert cell["field"] == "config_file"
    assert cell["unsandboxed"] is True
    assert "/mnt/cfg/swift_map.yaml" in cell["code"]
    assert "NOT surfaced" in cell["code"] and "inline transform_config" in cell["code"]


def test_surfaces_swift_config_file_alias_and_no_config_file_is_not_flagged():
    # camelCase alias flags too; and an inline-only Swift (no config_file) emits NO
    # config_file cell -- only its surfaceable python_expression fields.
    flagged = surface_code_cells({"components": [{"id": "sw", "type": "SwiftTransformer",
        "config": {"config_file": "cfg.yaml"}}]})
    assert any(c["field"] == "config_file" and c["unsandboxed"] is True for c in flagged)
    inline = surface_code_cells({"components": [{"id": "sw", "type": "SwiftTransformer",
        "config": {"transform_config": {"output_fields": [
            {"name": "A", "python_expression": "input_row['x']"}]}}}]})
    assert all(c["field"] != "config_file" for c in inline)
    assert any(c["field"].endswith("python_expression") for c in inline)


# ---- RowGenerator + RunIf eval cells (M1) ---------------------------------

def test_surfaces_rowgenerator_array_expression():
    job = {"components": [{"id": "rg", "type": "RowGenerator", "config": {
        "values": [{"column": "c", "array": "random.randint(1,9)"}]}}]}
    cells = surface_code_cells(job)
    assert any(c["component"] == "rg" and "random.randint" in c["code"] for c in cells)


def test_surfaces_runif_condition():
    job = {"components": [], "triggers": [{"id": "t1", "type": "RunIf", "from": "a", "to": "b",
        "condition": "globalMap.get('x') == 1"}]}
    cells = surface_code_cells(job)
    assert any(c.get("field") == "condition" and "globalMap" in c["code"] for c in cells)


def test_runif_edge_cases_dedup_and_multiple_branches():
    # Malformed entries tolerated; non-RunIf triggers ignored; blank conditions
    # skipped; a duplicate trigger id collapses; and TWO distinct RunIf branches
    # from the SAME source component both surface (dedup keys on trigger identity,
    # not (from, "condition") -- the gate must never drop a code-bearing cell).
    job = {"components": [], "triggers": [
        None, 5,                                                # malformed -> tolerated
        {"type": "OnSubjobOk", "from": "a", "to": "b"},         # not RunIf -> skipped
        {"id": "b0", "type": "RunIf", "from": "a", "condition": "   "},  # blank -> skipped
        {"id": "t1", "type": "runif", "from": "src", "condition": "globalMap.get('x') == 1"},
        {"id": "t2", "type": "RunIf", "from": "src", "condition": "globalMap.get('y') == 2"},
        {"id": "t1", "type": "RunIf", "from": "src", "condition": "globalMap.get('z') == 3"},  # dup id
    ]}
    cells = surface_code_cells(job)
    conds = [c["code"] for c in cells if c["field"] == "condition"]
    assert "globalMap.get('x') == 1" in conds          # branch 1 from src
    assert "globalMap.get('y') == 2" in conds          # branch 2 from src -- NOT deduped away
    assert "globalMap.get('z') == 3" not in conds       # duplicate trigger id collapses
    assert len(conds) == 2
    assert all(c["unsandboxed"] is False and c["type"].lower() == "runif"
               for c in cells if c["field"] == "condition")


def test_surface_non_dict_job_returns_empty():
    assert surface_code_cells("nope") == []
    assert surface_code_cells(None) == []


# ---- dedup + ordering -----------------------------------------------------

def test_dedup_prefers_explicit_unsandboxed_flag():
    # A python_dataframe whose python_code ALSO carries a {{java}} marker: the
    # explicit rule (unsandboxed True) must win over the generic marker rule,
    # and the (component, field) pair must appear exactly once.
    job = {"components": [
        {"id": "pdf", "type": "PythonDataFrameComponent",
         "config": {"python_code": "x = '{{java}}'"}}]}
    cells = surface_code_cells(job)
    pdf = [c for c in cells if c["component"] == "pdf" and c["field"] == "python_code"]
    assert len(pdf) == 1 and pdf[0]["unsandboxed"] is True


def test_ordering_unsandboxed_first_then_component_id():
    job = {"components": [
        {"id": "zzz", "type": "tPython", "config": {"python_code": "pass"}},
        {"id": "aaa", "type": "tPythonDataFrame", "config": {"python_code": "df"}},
        {"id": "mmm", "type": "tJava", "config": {"java_code": "x;"}},
    ]}
    cells = surface_code_cells(job)
    assert cells[0]["component"] == "aaa" and cells[0]["unsandboxed"] is True
    rest = [c["component"] for c in cells[1:]]
    assert all(c["unsandboxed"] is False for c in cells[1:])
    assert rest == sorted(rest)          # sandboxed cells ordered by component id


def test_empty_string_code_not_surfaced():
    job = {"components": [
        {"id": "pdf", "type": "tPythonDataFrame", "config": {"python_code": "   "}}]}
    assert surface_code_cells(job) == []


def test_missing_or_malformed_shapes_do_not_crash():
    assert surface_code_cells({}) == []
    assert surface_code_cells({"components": "nope"}) == []
    assert surface_code_cells({"components": [None, 5, {"id": "a"}]}) == []


# ---- CLI edge cases -------------------------------------------------------

def test_cli_missing_file_returns_two(tmp_path):
    rc = main(["--job", str(tmp_path / "nope.json")])
    assert rc == 2


def test_cli_non_dict_job_returns_two(tmp_path):
    p = tmp_path / "job.json"
    p.write_text(json.dumps([1, 2, 3]))
    assert main(["--job", str(p)]) == 2


def test_cli_empty_job_zero_cells_exit_zero(tmp_path, capsys):
    p = tmp_path / "job.json"
    p.write_text(json.dumps({"components": []}))
    rc = main(["--job", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == []


def test_cli_out_file_written(tmp_path):
    p = tmp_path / "job.json"
    p.write_text(json.dumps({"components": [
        {"id": "pdf", "type": "tPythonDataFrame", "config": {"python_code": "df"}}]}))
    outp = tmp_path / "cells.json"
    rc = main(["--job", str(p), "--out", str(outp)])
    assert rc == 0
    cells = json.loads(outp.read_text())
    assert cells[0]["unsandboxed"] is True and cells[0]["code"] == "df"
