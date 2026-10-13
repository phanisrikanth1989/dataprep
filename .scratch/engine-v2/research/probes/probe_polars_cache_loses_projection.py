"""Polars 1.44.2: an explicit LazyFrame.cache() can make a sink write wrong columns.

Run: .venv/bin/python .scratch/engine-v2/research/probes/probe_polars_cache_loses_projection.py

Observed 2026-10-06 on polars 1.44.2 (macOS arm64), both the streaming and
the in-memory engine. When a `select`/`drop` sits between an explicitly
cached frame and a frame that two plans of one `collect_all` read, the
projection is lost: the sink writes the dropped column too. With no
explicit cache the output is right (Polars may then read the source twice).
Each case below prints OK or WRONG; the scratch files it writes land in the
current folder.

Consequence for v2: components and the engine never call `.cache()`.
"""
import polars as pl, itertools
t = "p11.csv"
def run(label, plans_fn):
    for eng in ("streaming", "in-memory"):
        plans = plans_fn()
        pl.collect_all(plans, engine=eng)
        head = open(t).read().splitlines()[0]
        print(f"{'OK   ' if head == 'n,s' else 'WRONG'} {label:62s} {eng:10s} header={head}")
def base(): return pl.LazyFrame({"n": [1, 2], "s": ["a", "b"]}).with_columns(pl.col("n").is_null().alias("__v"))
def a():  # single explicit cache at the fork; main used by sink + count (CSE)
    b = base().cache(); m = b.drop("__v")
    return [m.sink_csv(t, lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())]
def b_():  # no explicit cache at all
    b = base(); m = b.drop("__v")
    return [m.sink_csv(t, lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())]
def c():  # single explicit cache, main with more work on top
    b = base().cache(); m = b.drop("__v").with_columns(pl.col("s").str.to_uppercase())
    return [m.sink_csv(t, lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())]
def d():  # explicit cache only on the outer frame
    b = base(); m = b.drop("__v").cache()
    return [m.sink_csv(t, lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())]
def e():  # two explicit caches, real work between them
    b = base().cache(); m = b.drop("__v").with_columns(pl.col("s").str.to_uppercase()).cache()
    return [m.sink_csv(t, lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())]
def f():  # two explicit caches, filter between
    b = base().cache(); m = b.filter(~pl.col("__v")).drop("__v").cache()
    return [m.sink_csv(t, lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())]
def g():  # single explicit cache, filter + drop, sink and count via CSE
    b = base().cache(); m = b.filter(~pl.col("__v")).drop("__v")
    return [m.sink_csv(t, lazy=True), m.select(pl.len()), b.filter(pl.col("__v")).select(pl.len())]
def h():  # two sinks off one explicit cache, each a projection
    b = base().cache()
    return [b.drop("__v").sink_csv(t, lazy=True), b.select("__v").sink_csv("p11b.csv", lazy=True)]
def i():  # two explicit caches, projection between, only sinks
    b = base().cache(); m = b.drop("__v").cache()
    return [m.sink_csv(t, lazy=True), m.sink_csv("p11b.csv", lazy=True), b.select("__v").sink_csv("p11c.csv", lazy=True)]
for label, fn in [("single explicit cache at fork; sink+count on main (CSE)", a), ("no explicit cache", b_), ("single explicit cache; work above", c),
                  ("explicit cache on outer only", d), ("two explicit caches; work between", e), ("two explicit caches; filter+drop between", f),
                  ("single explicit cache; filter+drop; sink+count (CSE)", g), ("two sinks off one explicit cache", h), ("two explicit caches, projection between, sinks only", i)]:
    run(label, fn)
