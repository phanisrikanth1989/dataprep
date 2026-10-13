"""Follow-up probes of src/v2 as found at commit cf01691a (2026-10-05).

Covers findings 6, 7 and 8 in ../2026-10-05-v2-as-found.md: iterate fan-out,
nested iterate, and a job that declares no context variables.
Run from anywhere:
    .venv/bin/python .scratch/engine-v2/research/probes/probe_v2_b.py
Writes only to a fresh system temp directory. Not tests; see probe_v2.py.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = str(Path(__file__).resolve().parents[4])
SCRATCH = tempfile.mkdtemp(prefix="v2_probe_")
tempfile.tempdir = SCRATCH
sys.path.insert(0, ROOT)

import logging  # noqa: E402

logging.disable(logging.CRITICAL)

from src.v2.engine import PyETLEngine  # noqa: E402

INT = [{"name": "id", "type": "integer"}]


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


def read(path):
    return open(path).read().replace("\n", "|") if os.path.exists(path) else "MISSING"


def src(cid, path):
    return {"id": cid, "type": "file_input_delimited", "config": {"path": path, "schema": INT}}


def sink(cid, path):
    return {"id": cid, "type": "file_output_delimited",
            "config": {"path": path, "append": True, "has_header": False}}


def iterate_job(d, context):
    job = {"name": "it", "components": [
        {"id": "fl", "type": "file_list", "config": {
            "directory": f"{d}/in", "files": [{"filemask": "*.csv"}], "order_by": "FILENAME"}},
        src("src", "${context.fl_CURRENT_FILEPATH}"), sink("out1", f"{d}/o1.csv")],
        "flows": [{"source": "fl", "target": "src"}, {"source": "src", "target": "out1"}]}
    if context is not None:
        job["context"] = context
    return job


print("--- H0. same iterate job, with and without any declared context variable")
for label, ctx in (("no context declared", None), ("context={'x': 1}", {"x": 1})):
    d = tempfile.mkdtemp()
    os.mkdir(f"{d}/in")
    for i in (1, 2, 3):
        write(f"{d}/in/f{i}.csv", f"id\n{i}\n")
    res = PyETLEngine(iterate_job(d, ctx)).execute()
    print(f"   {label:22s}: status={res['status']} error={str(res.get('error'))[:70]!r} o1={read(f'{d}/o1.csv')}")

print("--- H. iterate (3 files) + fan-out to two sinks, context non-empty")
d = tempfile.mkdtemp()
os.mkdir(f"{d}/in")
for i in (1, 2, 3):
    write(f"{d}/in/f{i}.csv", f"id\n{i}\n")
job = iterate_job(d, {"x": 1})
job["components"].append(sink("out2", f"{d}/o2.csv"))
job["flows"].append({"source": "src", "target": "out2"})
res = PyETLEngine(job).execute()
print(f"   status={res['status']} error={res.get('error')} | o1={read(f'{d}/o1.csv')} o2={read(f'{d}/o2.csv')}")
print("   recorded stats for body component 'src':", res["components"].get("src"))

print("--- V. nested iterate: 2 files x 2 rows, inner body appends one '9' per run (expect 4)")
d = tempfile.mkdtemp()
os.mkdir(f"{d}/in")
for i in (1, 2):
    write(f"{d}/in/f{i}.csv", "id\n1\n2\n")
write(f"{d}/const.csv", "id\n9\n")
job = {"name": "v", "context": {"x": 1}, "components": [
    {"id": "a_fl", "type": "file_list", "config": {"directory": f"{d}/in", "files": [{"filemask": "*.csv"}]}},
    src("b_src", "${context.a_fl_CURRENT_FILEPATH}"),
    {"id": "c_f2i", "type": "flow_to_iterate", "config": {}},
    src("d_inner", f"{d}/const.csv"), sink("e_out", f"{d}/o.csv")],
    "flows": [{"source": "a_fl", "target": "b_src"}, {"source": "b_src", "target": "c_f2i"},
              {"source": "c_f2i", "target": "d_inner"}, {"source": "d_inner", "target": "e_out"}]}
res = PyETLEngine(job).execute()
print(f"   status={res['status']} error={res.get('error')} | inner-body runs={read(f'{d}/o.csv').count('9')}")

print("--- CL. context_load into a job that declares no context, staged so ordering is right")
d = tempfile.mkdtemp()
write(f"{d}/ctx.properties", f"in_file={d}/a.csv\n")
write(f"{d}/a.csv", "id\n7\n")
job = {"name": "cl", "components": [
    {"id": "a_ctx", "type": "context_load", "config": {"path": f"{d}/ctx.properties"}},
    src("b_src", "${context.in_file}"),
    {"id": "c_out", "type": "file_output_delimited", "config": {"path": f"{d}/out.csv", "has_header": False}}],
    "flows": [{"source": "b_src", "target": "c_out"}],
    "triggers": [{"source": "a_ctx", "target": "b_src", "type": "on_success"}]}
for label, ctx in (("no context declared", None), ("context={'x': 1}", {"x": 1})):
    j = dict(job)
    if ctx is not None:
        j["context"] = ctx
    if os.path.exists(f"{d}/out.csv"):
        os.remove(f"{d}/out.csv")
    res = PyETLEngine(j).execute()
    errs = [s["error"] for s in res.get("stages", []) if s.get("error")]
    print(f"   {label:22s}: status={res['status']} out={read(f'{d}/out.csv')} stage_errors={[e[:60] for e in errs]}")
