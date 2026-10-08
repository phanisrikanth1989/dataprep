"""The two engines on the performance-bar cases; behind the answer in
../../issues/05-performance-bar.md. Read-only: imports from src/
and changes nothing there. Run from anywhere:

    E=.scratch/engine-v2/research/probes/probe_performance_bar_engines.py
    .venv/bin/python $E v1 <csv> <die_on_error: true|false> <encoding>
    .venv/bin/python $E as-found

`v1` times v1's FileInputDelimited, twice, on a file written by
`probe_performance_bar.py gen` (clean.csv, dirty.csv or latin.csv). It is a
scale reference only: one component, no job around it.

`as-found` runs v2's file_input_delimited as imported (commit cf01691a) on six
small files. It documents the starting point and will stop working as the
engine is rebuilt.
"""
import logging
import os
import resource
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = str(Path(__file__).resolve().parents[4])
sys.path.insert(0, ROOT)
logging.disable(logging.CRITICAL)


def v1(path, die_on_error, encoding):
    from src.v1.engine.components.file.file_input_delimited import FileInputDelimited
    from src.v1.engine.context_manager import ContextManager
    from src.v1.engine.global_map import GlobalMap

    # v1's engine takes date_pattern as a strftime pattern. Given yyyy-MM-dd it
    # sends every row to reject.
    schema = [
        {"name": "id", "type": "int"}, {"name": "cust", "type": "str"}, {"name": "name", "type": "str"},
        {"name": "city", "type": "str"}, {"name": "amount", "type": "float"}, {"name": "qty", "type": "int"},
        {"name": "price", "type": "float"}, {"name": "active", "type": "bool"},
        {"name": "trade_date", "type": "datetime", "date_pattern": "%Y-%m-%d"}, {"name": "note", "type": "str"},
    ]
    cfg = {"filepath": path, "fieldseparator": ";", "header_rows": 1, "encoding": encoding, "die_on_error": die_on_error}
    times = []
    for _ in range(2):
        comp = FileInputDelimited(component_id="in_1", config=cfg, global_map=GlobalMap(), context_manager=ContextManager())
        comp.output_schema = schema
        t0 = time.perf_counter()
        out = comp.execute(None)
        times.append(round(time.perf_counter() - t0, 2))
    main, reject = out.get("main"), out.get("reject")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss = rss if sys.platform == "darwin" else rss * 1024
    print(
        f"v1 FileInputDelimited die_on_error={die_on_error} encoding={encoding}: seconds={times}, "
        f"main={None if main is None else main.shape}, reject={None if reject is None else reject.shape}, "
        f"peak_rss_mb={rss / 1e6:.0f}"
    )


def as_found():
    from src.v2.components.file.file_input_delimited import FileInputDelimited

    d = tempfile.mkdtemp(prefix="v2_bar_probe_")

    def write(name, text):
        p = os.path.join(d, name)
        with open(p, "w") as f:
            f.write(text)
        return p

    def run(label, cfg):
        try:
            out = FileInputDelimited("in_1", cfg).apply({})
            got = {k: v.collect() for k, v in out.items()}
            print(f"{label:52s} OK   " + ", ".join(f"{k}={v.shape}" for k, v in got.items()))
        except Exception as e:  # the failure text is the finding
            print(f"{label:52s} FAIL {type(e).__name__}: {str(e).splitlines()[0][:100]}")

    numbers = [{"name": "id", "type": "integer"}, {"name": "amount", "type": "float"}]
    flags = [{"name": "id", "type": "integer"}, {"name": "active", "type": "boolean"}]
    body = "id;amount\n1;10.5\n2;20.5\n3;30.5\n"
    base = {"delimiter": ";", "has_header": True}
    fit, misfit = write("fit.csv", body + "9;0\n"), write("misfit.csv", body + "TRAILER;3\n")
    bools = write("bools.csv", "id;active\n1;true\n2;false\n")
    bad = write("bad.csv", "id;amount\n1;10.5\n2;oops\n3;30.5\n")

    run("footer 1, trailer fits the schema, die_on_error true", {**base, "path": fit, "schema": numbers, "footer_rows": 1})
    run("footer 1, trailer TRAILER;3, die_on_error true", {**base, "path": misfit, "schema": numbers, "footer_rows": 1})
    run("footer 1, trailer TRAILER;3, die_on_error false",
        {**base, "path": misfit, "schema": numbers, "footer_rows": 1, "die_on_error": False})
    run("boolean column, die_on_error true", {**base, "path": bools, "schema": flags})
    run("boolean column, die_on_error false", {**base, "path": bools, "schema": flags, "die_on_error": False})
    run("one bad number, die_on_error false", {**base, "path": bad, "schema": numbers, "die_on_error": False})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "v1" and len(sys.argv) == 5:
        v1(sys.argv[2], sys.argv[3] == "true", sys.argv[4])
    elif cmd == "as-found":
        as_found()
    else:
        raise SystemExit(__doc__)
