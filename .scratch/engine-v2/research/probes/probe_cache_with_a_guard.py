"""The shapes that made cache() write wrong columns, tried with each way of guarding the cache.
Run: .venv/bin/python .scratch/engine-v2/research/probes/probe_cache_with_a_guard.py
Tried 2026-10-06 on polars 1.44.2 (macOS arm64) for ticket 31. It writes into a
temporary folder of its own.
"""
import itertools
import os
import tempfile

import polars as pl

HERE = tempfile.mkdtemp(prefix="v2_probe_")
OUT = [os.path.join(HERE, f"shape_{n}.csv") for n in range(3)]


def base():
    return pl.LazyFrame({"n": [1, 2, 3], "s": ["a", "b", "c"], "t": ["x", "y", "z"]}).with_columns(pl.col("n").is_null().alias("__v"))


def opaque(frame, projection):
    return frame.map_batches(lambda batch: batch, streamable=True, validate_output_schema=False,
                             projection_pushdown=projection, predicate_pushdown=False, slice_pushdown=False)


GUARDS = {
    "plain cache()": lambda frame: frame.cache(),
    "cache() + closed barrier": lambda frame: opaque(frame.cache(), False),
    "cache() + barrier, columns let through": lambda frame: opaque(frame.cache(), True),
    "closed barrier + cache()": lambda frame: opaque(frame, False).cache(),
}

# Each shape: (what it is, builder returning (plans, {file: expected header})).
def shape_a(share):   # the first shape that went wrong: a drop on a shared frame, read by a sink and a count
    b = share(base()); m = b.drop("__v")
    return [m.sink_csv(OUT[0], lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())], {OUT[0]: "n,s,t"}

def shape_i(share):   # the second: two shared frames with nothing but a drop between them
    b = share(base()); m = share(b.drop("__v"))
    return [m.sink_csv(OUT[0], lazy=True), m.sink_csv(OUT[1], lazy=True), b.select("__v").sink_csv(OUT[2], lazy=True)], \
           {OUT[0]: "n,s,t", OUT[1]: "n,s,t", OUT[2]: "__v"}

def shape_chain(share):   # three shared frames in a row, a select between each
    b = share(base()); m = share(b.select("n", "s", "t")); k = share(m.select("n", "s"))
    return [k.sink_csv(OUT[0], lazy=True), k.select("n").sink_csv(OUT[1], lazy=True), m.sink_csv(OUT[2], lazy=True),
            b.select(pl.len())], {OUT[0]: "n,s", OUT[1]: "n", OUT[2]: "n,s,t"}

def shape_rename(share):   # a shared frame, then a select that renames and reorders, shared again
    b = share(base()); m = share(b.select(pl.col("t").alias("tt"), "n"))
    return [m.sink_csv(OUT[0], lazy=True), m.filter(pl.col("n") > 1).sink_csv(OUT[1], lazy=True),
            b.drop("__v").sink_csv(OUT[2], lazy=True)], {OUT[0]: "tt,n", OUT[1]: "tt,n", OUT[2]: "n,s,t"}

def shape_filters(share):   # a shared frame whose readers filter differently: no reader may see the other's rows
    b = share(base())
    return [b.filter(pl.col("n") > 1).drop("__v").sink_csv(OUT[0], lazy=True),
            b.filter(pl.col("n") <= 1).select("s").sink_csv(OUT[1], lazy=True)], {OUT[0]: "n,s,t", OUT[1]: "s"}

SHAPES = {"drop, read by a sink and a count": shape_a, "two shared frames, a drop between": shape_i,
          "three shared frames in a row": shape_chain, "rename and reorder between": shape_rename,
          "readers that filter differently": shape_filters}
for (name, shape), (guard, share), engine, cse in itertools.product(SHAPES.items(), GUARDS.items(), ["streaming"], [True, False]):
    plans, expected = shape(share)
    try:
        pl.collect_all(plans, engine=engine, optimizations=pl.QueryOptFlags(comm_subplan_elim=cse))
        wrong = {os.path.basename(path): open(path).read().splitlines()[0] for path, head in expected.items()
                 if open(path).read().splitlines()[0] != head}
        rows = {os.path.basename(path): len(open(path).read().splitlines()) - 1 for path in expected}
        verdict = "OK   " if not wrong else "WRONG"
        print(f"{verdict} {name:34} {guard:40} sharing by Polars {'on ' if cse else 'off'} {wrong or ''} rows {list(rows.values())}")
    except Exception as exc:
        print(f"FAILS {name:34} {guard:40} sharing by Polars {'on ' if cse else 'off'} {' '.join(str(exc).split())[:90]}")
