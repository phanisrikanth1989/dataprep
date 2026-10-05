"""Read-only probes of src/v2 as found at commit cf01691a (2026-10-05).

Each check reproduces one or more findings in ../2026-10-05-v2-as-found.md.
Run from anywhere:
    .venv/bin/python .scratch/engine-v2/research/probes/probe_v2.py
Writes only to a fresh system temp directory. These document the starting
point; they are not tests and will stop working as the engine is rebuilt.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = str(Path(__file__).resolve().parents[4])
SCRATCH = tempfile.mkdtemp(prefix="v2_probe_")
tempfile.tempdir = SCRATCH
sys.path.insert(0, ROOT)

import logging  # noqa: E402

logging.disable(logging.CRITICAL)

import polars as pl  # noqa: E402

from src.v2.engine import PyETLEngine  # noqa: E402
from src.v2.expressions import compile_expression  # noqa: E402
from src.v2.expressions.compiler import ExpressionCompiler  # noqa: E402
from src.v2.expressions.tokenizer import Tokenizer  # noqa: E402
from src.v2.components.registry import REGISTRY  # noqa: E402
from src.v2.execution.trigger import TriggerEvaluator  # noqa: E402

INT = [{"name": "id", "type": "integer"}]
ID_NAME = [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


def read(path):
    return open(path).read().replace("\n", "|") if os.path.exists(path) else "MISSING"


def check(label):
    def deco(fn):
        print(f"\n--- {label}")
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"   RAISED {type(e).__name__}: {str(e)[:300]}")
        return fn
    return deco


def src(cid, path, schema=None, **extra):
    cfg = {"path": path, "schema": schema or INT}
    cfg.update(extra)
    return {"id": cid, "type": "file_input_delimited", "config": cfg}


def sink(cid, path, **extra):
    cfg = {"path": path}
    cfg.update(extra)
    return {"id": cid, "type": "file_output_delimited", "config": cfg}


print("polars", pl.__version__, "| python", sys.version.split()[0])


@check("A. parser: trailing tokens after a complete expression")
def _():
    df = pl.DataFrame({"amount": [50, 150], "foo": [1, 2]})
    for s in ["amount > 100 garbage here", "foo(1, 2)", "amount > 100 )", "amount 5", "Customers.name"]:
        try:
            e = compile_expression(s)
        except Exception as ex:  # noqa: BLE001
            print(f"   {s!r:30s} -> compile {type(ex).__name__}: {str(ex)[:90]}")
            continue
        try:
            out = df.select(e.alias("r")).to_series().to_list()
            print(f"   {s!r:30s} -> ACCEPTED as [{e}] result={out}")
        except Exception as ex:  # noqa: BLE001
            print(f"   {s!r:30s} -> ACCEPTED as [{e}] then eval {type(ex).__name__}")


@check("B. null comparisons in the DSL")
def _():
    df = pl.DataFrame({"id": [1, 2, 3, 4], "status": ["A", None, "B", "A"]})
    for s in ["status == null", "status != null", "status == 'A'", "status != 'A'", "ISNULL(status)"]:
        print(f"   {s!r:18s} -> {df.select(compile_expression(s).alias('r')).to_series().to_list()}")


@check("C. FilterRows with reject: row conservation when the condition is null")
def _():
    df = pl.DataFrame({"id": [1, 2, 3, 4], "status": ["A", None, "B", "A"]})
    c = REGISTRY.get("filter_rows")("f", {"condition": "status == 'A'", "reject_output": True})
    out = c.apply({"main": df.lazy()})
    m, r = out["main"].collect(), out["reject"].collect()
    print(f"   in={len(df)} main={len(m)} reject={len(r)} unaccounted={len(df) - len(m) - len(r)}")


@check("D. Map output expression that is a bare keyword/literal")
def _():
    df = pl.DataFrame({"id": [1, 2]})
    for expr in ["null", "true", "'x'", "1", "id"]:
        cfg = {"outputs": [{"name": "main", "columns": [
            {"name": "id", "expression": "id"}, {"name": "c", "expression": expr}]}]}
        try:
            out = REGISTRY.get("map")("m", cfg).apply({"main": df.lazy()})["main"].collect()
            print(f"   expression {expr!r:6s} -> OK {out['c'].to_list()} ({out['c'].dtype})")
        except Exception as ex:  # noqa: BLE001
            print(f"   expression {expr!r:6s} -> {type(ex).__name__}: {str(ex)[:80]!r}")


@check("E. Unite fed by two flows that both use the default input port")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", "id,name\n1,a\n2,b\n")
    write(f"{d}/b.csv", "id,name\n3,c\n4,d\n")
    job = {"name": "e", "components": [
        src("src_a", f"{d}/a.csv", ID_NAME), src("src_b", f"{d}/b.csv", ID_NAME),
        {"id": "uni", "type": "unite", "config": {}}, sink("out", f"{d}/out.csv")],
        "flows": [{"source": "src_a", "target": "uni"}, {"source": "src_b", "target": "uni"},
                  {"source": "uni", "target": "out"}]}
    res = PyETLEngine(job).execute()
    print("   status:", res["status"], res.get("error"))
    print("   out.csv:", read(f"{d}/out.csv"))
    print("   sink stats:", res["components"].get("out"))


@check("F. Unite input order across PYTHONHASHSEED (distinct input ports)")
def _():
    child = textwrap.dedent('''
        import sys, tempfile, logging
        sys.dont_write_bytecode = True
        sys.path.insert(0, %r)
        tempfile.tempdir = %r
        logging.disable(logging.CRITICAL)
        from src.v2.engine import PyETLEngine
        d = tempfile.mkdtemp()
        for n, v in (("a", 1), ("b", 2), ("c", 3)):
            open(f"{d}/{n}.csv", "w").write(f"id\\n{v}\\n")
        s = [{"name": "id", "type": "integer"}]
        comps = [{"id": f"src_{n}", "type": "file_input_delimited",
                  "config": {"path": f"{d}/{n}.csv", "schema": s}} for n in "abc"]
        comps += [{"id": "uni", "type": "unite", "config": {}},
                  {"id": "out", "type": "file_output_delimited",
                   "config": {"path": f"{d}/out.csv", "has_header": False}}]
        flows = [{"source": f"src_{n}", "target": "uni", "input": f"in{i}"} for i, n in enumerate("abc")]
        flows.append({"source": "uni", "target": "out"})
        r = PyETLEngine({"name": "f", "components": comps, "flows": flows}).execute()
        print(r["status"], open(f"{d}/out.csv").read().split())
    ''') % (ROOT, SCRATCH)
    seen = {}
    for seed in range(12):
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        out = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env)
        seen.setdefault(out.stdout.strip() or out.stderr.strip()[-160:], []).append(seed)
    for k, v in seen.items():
        print(f"   seeds {v}: {k}")


@check("G. port-name mismatch: uniq_row emits 'unique', flow uses default 'main'")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", "id,name\n1,a\n1,a\n2,b\n")
    job = {"name": "g", "components": [
        src("src", f"{d}/a.csv", ID_NAME),
        {"id": "uq", "type": "uniq_row", "config": {"key_columns": [{"column": "id"}]}},
        sink("out", f"{d}/out.csv")],
        "flows": [{"source": "src", "target": "uq"}, {"source": "uq", "target": "out"}]}
    res = PyETLEngine(job).execute()
    print("   status:", res["status"], res.get("error"), "| out.csv:", read(f"{d}/out.csv"))


@check("H. iterate (3 files) with a fan-out: one source feeding two sinks")
def _():
    d = tempfile.mkdtemp()
    os.mkdir(f"{d}/in")
    for i in (1, 2, 3):
        write(f"{d}/in/f{i}.csv", f"id\n{i}\n")
    job = {"name": "h", "components": [
        {"id": "fl", "type": "file_list", "config": {
            "directory": f"{d}/in", "files": [{"filemask": "*.csv"}], "order_by": "FILENAME"}},
        src("src", "${context.fl_CURRENT_FILEPATH}"),
        sink("out1", f"{d}/o1.csv", append=True, has_header=False),
        sink("out2", f"{d}/o2.csv", append=True, has_header=False)],
        "flows": [{"source": "fl", "target": "src"}, {"source": "src", "target": "out1"},
                  {"source": "src", "target": "out2"}]}
    res = PyETLEngine(job).execute()
    print("   status:", res["status"], res.get("error"))
    print("   o1.csv:", read(f"{d}/o1.csv"), "| o2.csv:", read(f"{d}/o2.csv"))


@check("J. Talend-style type names (id_Integer) through die_on_error true/false")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", "id,qty\n1,5\nx,6\n")
    for die in (True, False):
        schema = [{"name": "id", "type": "id_Integer"}, {"name": "qty", "type": "id_Integer"}]
        c = REGISTRY.get("file_input_delimited")("s", {"path": f"{d}/a.csv", "schema": schema, "die_on_error": die})
        try:
            out = c.apply({})
            m = out["main"].collect()
            rej = out["reject"].collect().height if "reject" in out else None
            print(f"   die_on_error={die}: main rows={m.height} dtypes={dict(m.schema)} reject rows={rej}")
        except Exception as ex:  # noqa: BLE001
            print(f"   die_on_error={die}: {type(ex).__name__}: {str(ex)[:110]!r}")
    c = REGISTRY.get("file_input_delimited")("s", {"path": f"{d}/a.csv", "die_on_error": False, "schema": [
        {"name": "id", "type": "integer"}, {"name": "qty", "type": "integer"}]})
    out = c.apply({})
    print(f"   (control, type='integer', die_on_error=False): main rows={out['main'].collect().height} "
          f"reject rows={out['reject'].collect().height if 'reject' in out else None}")


@check("K. tokenizer FUNCTIONS vs compiler function registry")
def _():
    tok, comp = set(Tokenizer.FUNCTIONS), set(ExpressionCompiler()._functions)
    print("   named in tokenizer, no implementation:", sorted(tok - comp))
    print("   implemented, unreachable from tokenizer:", sorted(comp - tok))


@check("L. MIN(a, b) / MAX(a, b)")
def _():
    df = pl.DataFrame({"a": [1, 5, 3], "b": [4, 2, 9]})
    for s in ["MIN(a, b)", "MAX(a, b)"]:
        print(f"   {s} over a=[1,5,3] b=[4,2,9] -> {df.with_columns(compile_expression(s).alias('r'))['r'].to_list()}")


@check("M. Map: two inner-join lookups + lookup_reject_output")
def _():
    main = pl.DataFrame({"id": [1, 2, 3], "k1": ["a", "b", "z"], "k2": ["x", "q", "y"]}).lazy()
    l1 = pl.DataFrame({"k": ["a", "b"], "v1": [10, 20]}).lazy()
    l2 = pl.DataFrame({"k": ["x", "y"], "v2": [100, 200]}).lazy()
    cfg = {"lookups": [{"name": "l1", "keys": [{"main": "k1", "lookup": "k"}], "join_type": "inner"},
                       {"name": "l2", "keys": [{"main": "k2", "lookup": "k"}], "join_type": "inner"}],
           "lookup_reject_output": "rej",
           "outputs": [{"name": "main", "columns": [{"name": "id", "expression": "id"}]},
                       {"name": "rej", "columns": []}]}
    c = REGISTRY.get("map")("m", cfg)
    print("   validate:", c.validate())
    out = c.apply({"main": main, "l1": l1, "l2": l2})
    for k, v in out.items():
        try:
            print(f"   {k}: {v.collect().to_dicts()}")
        except Exception as ex:  # noqa: BLE001
            print(f"   {k}: {type(ex).__name__}: {str(ex)[:140]!r}")


@check("N. Map: reference the lookup's KEY column as l1.k")
def _():
    main = pl.DataFrame({"id": [1, 2], "k1": ["a", "b"]}).lazy()
    l1 = pl.DataFrame({"k": ["a", "b"], "v1": [10, 20]}).lazy()
    cfg = {"lookups": [{"name": "l1", "keys": [{"main": "k1", "lookup": "k"}], "join_type": "left"}],
           "outputs": [{"name": "main", "columns": [{"name": "id", "expression": "id"},
                                                    {"name": "lk", "expression": "l1.k"}]}]}
    try:
        print("  ", REGISTRY.get("map")("m", cfg).apply({"main": main, "l1": l1})["main"].collect().to_dicts())
    except Exception as ex:  # noqa: BLE001
        print(f"   {type(ex).__name__}: {str(ex)[:100]!r}")


@check("O. FileInputFullRow: lines containing double quotes")
def _():
    d = tempfile.mkdtemp()
    lines = ['plain line', '"quoted start" and more', 'he said "hi"', '"unbalanced quote', 'last line']
    write(f"{d}/t.txt", "\n".join(lines) + "\n")
    c = REGISTRY.get("file_input_full_row")("r", {"path": f"{d}/t.txt", "schema": [{"name": "line", "type": "string"}]})
    out = c.apply({})["main"].collect()
    print(f"   file has {len(lines)} lines; read {out.height}: {out['line'].to_list()}")


@check("P. scalar routine inside an expression: dtype and what can consume it")
def _():
    from src.v2.routines import RoutineManager
    reg = RoutineManager().get_registry()
    df = pl.DataFrame({"name": ["a", "b"]})
    out = df.lazy().select(compile_expression("DemoRoutine.greet(name)", routine_registry=reg).alias("g")).collect()
    print("   dtype:", out["g"].dtype, out["g"].to_list())
    for label, fn in (("write_csv", lambda: out.write_csv()),
                      ("UPPER(routine)", lambda: df.lazy().select(compile_expression(
                          "UPPER(DemoRoutine.greet(name))", routine_registry=reg).alias("g")).collect().to_dicts())):
        try:
            print(f"   {label}: {fn()!r}")
        except Exception as ex:  # noqa: BLE001
            print(f"   {label} -> {type(ex).__name__}: {str(ex)[:110]!r}")


@check("Q. operator semantics (compare with Java: 7/2=3, -7%2=-1, null+'x'='nullx', 'n='+7='n=7')")
def _():
    df = pl.DataFrame({"i": [7, -7], "j": [2, 2], "s": ["a", None], "z": [0, 0]})
    for s in ["i / j", "i % j", "s + 'x'", "'n=' + i", "i / z", "CONCAT(s, 'x')", "TO_STRING(s)", "LENGTH(s)"]:
        try:
            r = df.select(compile_expression(s).alias("r"))["r"]
            print(f"   {s:16s} -> {r.to_list()} ({r.dtype})")
        except Exception as ex:  # noqa: BLE001
            print(f"   {s:16s} -> {type(ex).__name__}: {str(ex)[:90]!r}")


@check("R. CSV read of a STRING column: empty, quoted-empty, 'NaN', 'nan'")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", 'id,name\n1,\n2,""\n3,NaN\n4,nan\n5,x\n')
    c = REGISTRY.get("file_input_delimited")("s", {"path": f"{d}/a.csv", "schema": ID_NAME})
    print("   name column:", c.apply({})["main"].collect()["name"].to_list())


@check("S. which component is blamed when a lazy source's data is bad")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", "id\n1\nnot_a_number\n")
    job = {"name": "s", "components": [
        src("src", f"{d}/a.csv"), {"id": "flt", "type": "filter_rows", "config": {"condition": "id > 0"}},
        sink("out", f"{d}/out.csv")],
        "flows": [{"source": "src", "target": "flt"}, {"source": "flt", "target": "out"}]}
    res = PyETLEngine(job).execute()
    print("   status:", res["status"], "| error_type:", res.get("error_type"))
    print("   error text:", " ".join(str(res.get("error")).split())[:150])
    print("   components with recorded stats (i.e. 'completed'):", list(res["components"]))


@check("T. Excel native date cell with ISO vs non-ISO date_pattern")
def _():
    import datetime
    import xlsxwriter
    d = tempfile.mkdtemp()
    p = f"{d}/t.xlsx"
    wb = xlsxwriter.Workbook(p)
    ws = wb.add_worksheet()
    fmt = wb.add_format({"num_format": "dd/mm/yyyy"})
    ws.write(0, 0, "id")
    ws.write(0, 1, "dt")
    ws.write(1, 0, 1)
    ws.write_datetime(1, 1, datetime.date(2024, 1, 15), fmt)
    wb.close()
    for pat in ("%d/%m/%Y", "%Y-%m-%d"):
        c = REGISTRY.get("file_input_excel")("x", {"path": p, "schema": [
            {"name": "id", "type": "integer"}, {"name": "dt", "type": "date", "date_pattern": pat}]})
        try:
            print(f"   pattern {pat}: OK {c.apply({})['main'].collect().to_dicts()}")
        except Exception as ex:  # noqa: BLE001
            print(f"   pattern {pat}: {type(ex).__name__}: {' '.join(str(ex).split())[:120]!r}")


@check("U. context_load then a filter on context.threshold (job default 0, file says 100)")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/ctx.properties", "threshold=100\n")
    write(f"{d}/a.csv", "id\n5\n500\n")
    comps = [{"id": "a_ctx", "type": "context_load", "config": {"path": f"{d}/ctx.properties"}},
             src("b_src", f"{d}/a.csv"),
             {"id": "c_flt", "type": "filter_rows", "config": {"condition": "id > context.threshold"}},
             sink("d_out", f"{d}/out.csv", has_header=False)]
    flows = [{"source": "b_src", "target": "c_flt"}, {"source": "c_flt", "target": "d_out"}]
    base = {"name": "u", "context": {"threshold": 0}, "components": comps, "flows": flows}
    res = PyETLEngine(dict(base)).execute()
    print("   flat (no triggers):  status", res["status"], "| rows kept:", read(f"{d}/out.csv"))
    os.remove(f"{d}/out.csv")
    staged = dict(base, triggers=[{"source": "a_ctx", "target": "b_src", "type": "on_success"}])
    res = PyETLEngine(staged).execute()
    print("   staged (on_success): status", res["status"], "| rows kept:", read(f"{d}/out.csv"))


@check("V. nested iterate: 2 files x 2 rows each, inner body appends 1 row per run (expect 4)")
def _():
    d = tempfile.mkdtemp()
    os.mkdir(f"{d}/in")
    for i in (1, 2):
        write(f"{d}/in/f{i}.csv", "id\n1\n2\n")
    write(f"{d}/const.csv", "id\n9\n")
    job = {"name": "v", "components": [
        {"id": "a_fl", "type": "file_list", "config": {"directory": f"{d}/in", "files": [{"filemask": "*.csv"}]}},
        src("b_src", "${context.a_fl_CURRENT_FILEPATH}"),
        {"id": "c_f2i", "type": "flow_to_iterate", "config": {}},
        src("d_inner", f"{d}/const.csv"),
        sink("e_out", f"{d}/o.csv", append=True, has_header=False)],
        "flows": [{"source": "a_fl", "target": "b_src"}, {"source": "b_src", "target": "c_f2i"},
                  {"source": "c_f2i", "target": "d_inner"}, {"source": "d_inner", "target": "e_out"}]}
    res = PyETLEngine(job).execute()
    body = read(f"{d}/o.csv")
    print("   status:", res["status"], res.get("error"), "| inner-body runs:", body.count("9"))


@check("W. one source sending two outputs (main + reject) to the same target on different ports")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", "id\n1\n2\n3\n4\n")
    job = {"name": "w", "components": [
        src("src", f"{d}/a.csv"),
        {"id": "flt", "type": "filter_rows", "config": {"condition": "id > 2", "reject_output": True}},
        {"id": "uni", "type": "unite", "config": {}}, sink("out", f"{d}/out.csv", has_header=False)],
        "flows": [{"source": "src", "target": "flt"},
                  {"source": "flt", "output": "main", "target": "uni", "input": "in1"},
                  {"source": "flt", "output": "reject", "target": "uni", "input": "in2"},
                  {"source": "uni", "target": "out"}]}
    res = PyETLEngine(job).execute()
    print("   status:", res["status"], res.get("error"), "| 4 rows in, out.csv:", read(f"{d}/out.csv"))


@check("X. decimal columns and float output formatting")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", "id,amt,px\n1,30200.00,0.1\n2,10.10,0.2\n")
    schema = [{"name": "id", "type": "integer"}, {"name": "amt", "type": "decimal"}, {"name": "px", "type": "float"}]
    m = REGISTRY.get("file_input_delimited")("s", {"path": f"{d}/a.csv", "schema": schema}).apply({})["main"].collect()
    print("   dtypes:", dict(m.schema))
    for s in ["amt * 2", "TO_DECIMAL(amt) * 3", "px + 0.2", "TO_FLOAT(amt)"]:
        try:
            r = m.select(compile_expression(s).alias("r"))["r"]
            print(f"   {s:20s} -> {r.to_list()} ({r.dtype}) csv={r.to_frame().write_csv(include_header=False).split()}")
        except Exception as ex:  # noqa: BLE001
            print(f"   {s:20s} -> {type(ex).__name__}: {str(ex)[:80]!r}")


@check("Y. staged run: stage A fails with no on_failure handler; B is independent; C needs A")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/ok.csv", "id\n1\n")
    job = {"name": "y", "components": [
        src("a_src", f"{d}/does_not_exist.csv"), sink("a_out", f"{d}/a_out.csv"),
        src("b_src", f"{d}/ok.csv"), sink("b_out", f"{d}/b_out.csv"),
        src("c_src", f"{d}/ok.csv"), sink("c_out", f"{d}/c_out.csv")],
        "flows": [{"source": "a_src", "target": "a_out"}, {"source": "b_src", "target": "b_out"},
                  {"source": "c_src", "target": "c_out"}],
        "triggers": [{"source": "a_out", "target": "c_src", "type": "on_success"}]}
    res = PyETLEngine(job).execute()
    print("   job status:", res["status"], "| stages:", [(s["stage_id"], s["status"]) for s in res["stages"]])
    print("   b_out written after A failed:", os.path.exists(f"{d}/b_out.csv"))


@check("Z. trigger-condition language (separate from the expression DSL)")
def _():
    ctx = {"n": 5, "env": "prod"}
    for cond in ["${context.n} > 0", "context.n > 0", "env == prod", "anything",
                 "${context.n} > 0 && ${context.env} == 'prod'",
                 '((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE")) > 0']:
        try:
            print(f"   {cond[:58]!r:62s} -> {TriggerEvaluator._evaluate_condition(cond, ctx)}")
        except Exception as ex:  # noqa: BLE001
            print(f"   {cond[:58]!r:62s} -> {type(ex).__name__}: {str(ex)[:60]}")


@check("AA. unknown / misspelled config keys")
def _():
    d = tempfile.mkdtemp()
    write(f"{d}/a.csv", "id;name\n1;a\n")
    c = REGISTRY.get("file_input_delimited")("s", {"path": f"{d}/a.csv", "schema": ID_NAME, "delimeter": ";"})
    print("   validate() with misspelled 'delimeter':", c.validate())
    from src.v2.config import JobConfig
    j = JobConfig(name="x", engine="python", java_config={"enabled": True}, not_a_field=1)
    print("   JobConfig accepted unknown top-level keys; kept fields:", sorted(j.model_dump().keys()))


@check("AB. unresolved ${context.var} in a path")
def _():
    c = REGISTRY.get("file_input_delimited")("s", {"path": "${context.in_dir}/a.csv", "schema": INT}, context={})
    print("   validate():", c.validate(), "| resolved path:", c.resolve_context(c.config["path"]))
