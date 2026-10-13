"""Peak memory, file to file, behind the answer in ../../issues/05-performance-bar.md.

Does a job's memory grow with its input file? Each variant reads the CSV
written by `probe_performance_bar.py gen`, does one thing and writes a CSV.
Run one variant per process under the system `time`, from the repo root, at
two file sizes:

    M=.scratch/engine-v2/research/probes/probe_performance_bar_memory.py
    .venv/bin/python $M list
    /usr/bin/time -l .venv/bin/python $M <dir> <variant>    macOS: read "peak memory footprint"
    /usr/bin/time -v .venv/bin/python $M <dir> <variant>    Linux: read "Maximum resident set size"

`mem_copy` collects on the in-memory engine and then writes. Every other
variant goes scan -> sink_csv, which runs on the streaming engine.

Polars maps the input file into memory. macOS "peak memory footprint" leaves
those pages out; resident set size (the `peak_rss_mb` printed here, and the
Linux figure) counts them, so it grows with the file even when the job
streams. Observations only, for the machine and Polars version they ran on.
"""
import json
import os
import resource
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import polars as pl  # noqa: E402

import probe_performance_bar as P  # noqa: E402


def variants(p, out, out_reject):
    typed = lambda path, **kw: P.with_date(P.scan_typed(path, **kw))  # noqa: E731
    lookup = lambda: pl.scan_csv(p["lookup"], separator=P.SEP)  # noqa: E731
    sink = lambda lf: lf.sink_csv(out, separator=P.SEP)  # noqa: E731

    def mem_copy():
        typed(p["clean"]).collect().write_csv(out, separator=P.SEP)

    def lenient_main_and_reject():
        main, reject = P.lazy_validate(p["dirty"])
        pl.collect_all(
            [main.sink_csv(out, separator=P.SEP, lazy=True), reject.sink_csv(out_reject, separator=P.SEP, lazy=True)],
            engine="streaming",
        )

    def footer_count_first():
        n = P.scan_typed(p["clean"]).select(pl.len()).collect().item()
        sink(typed(p["clean"], n_rows=n - 1))

    def footer_count_in_plan():
        n = P.scan_typed(p["clean"]).select(pl.len().alias("__n"))
        lf = P.scan_typed(p["clean"]).with_row_index("__i").join(n, how="cross")
        sink(P.with_date(lf.filter(pl.col("__i") < pl.col("__n") - 1).drop("__i", "__n")))

    def footer_row_index_shift():
        lf = P.scan_typed(p["clean"]).with_row_index("__i")
        sink(P.with_date(lf.filter(pl.col("__i").shift(-1).is_not_null()).drop("__i")))

    def uniq_insensitive_first_ordered():
        lf = typed(p["clean"]).with_columns(pl.col("cust").str.to_lowercase().alias("__k"))
        sink(lf.unique(subset=["__k"], keep="first", maintain_order=True).drop("__k"))

    def join_one_left_order():
        lk = lookup().unique(subset=["cust"], keep="last", maintain_order=True)
        sink(typed(p["clean"]).join(lk, on="cust", how="left", maintain_order="left"))

    return {
        "mem_copy": mem_copy,
        "copy": lambda: sink(typed(p["clean"])),
        "lenient_main": lambda: sink(P.lazy_validate(p["dirty"])[0]),
        "lenient_main_and_reject": lenient_main_and_reject,
        "footer_position_filter": lambda: sink(
            P.with_date(P.scan_typed(p["clean"]).filter(pl.int_range(pl.len()) < pl.len() - 1))
        ),
        "footer_count_first": footer_count_first,
        "footer_count_in_plan": footer_count_in_plan,
        "footer_row_index_shift": footer_row_index_shift,
        "sort": lambda: sink(typed(p["clean"]).sort("amount")),
        "uniq_first_ordered": lambda: sink(typed(p["clean"]).unique(subset=["cust"], keep="first", maintain_order=True)),
        "uniq_any_unordered": lambda: sink(typed(p["clean"]).unique(subset=["cust"], keep="any", maintain_order=False)),
        "uniq_insensitive_first_ordered": uniq_insensitive_first_ordered,
        "group_unordered": lambda: sink(typed(p["clean"]).group_by("cust").agg(pl.col("amount").sum(), pl.len())),
        "group_ordered": lambda: sink(
            typed(p["clean"]).group_by("cust", maintain_order=True).agg(pl.col("amount").sum(), pl.len())
        ),
        "join_all_unordered": lambda: sink(typed(p["clean"]).join(lookup(), on="cust", how="left", maintain_order="none")),
        "join_all_left_order": lambda: sink(typed(p["clean"]).join(lookup(), on="cust", how="left", maintain_order="left")),
        "join_one_left_order": join_one_left_order,
    }


def main(d, what):
    p = P.paths(d)
    out = os.path.join(d, f"out_{what}.csv")
    out_reject = os.path.join(d, f"out_{what}_reject.csv")
    fn = variants(p, out, out_reject)[what]
    t0 = time.perf_counter()
    fn()
    seconds = time.perf_counter() - t0
    size = os.path.getsize(out)
    for f in (out, out_reject):
        if os.path.exists(f):
            os.remove(f)
    print(json.dumps({
        "variant": what,
        "input_mb": round(os.path.getsize(p["clean"]) / 1e6),
        "seconds": round(seconds, 3),
        "peak_rss_mb": P.peak_rss_mb(),
        "out_mb": round(size / 1e6),
        "polars": pl.__version__,
    }))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "list":
        print("\n".join(variants(P.paths("."), "", "")))
    elif len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        raise SystemExit(__doc__)
