"""A small model of the engine's nested outputs: how often each part runs, with and without explicit sharing.
Run: .venv/bin/python .scratch/engine-v2/research/probes/probe_nested_outputs_run_once.py
Tried 2026-10-06 on polars 1.44.2 (macOS arm64) for ticket 31. It writes into a
temporary folder of its own.
"""
import hashlib
import os
import tempfile
import sys

import polars as pl

ROWS = 200_000
HERE = tempfile.mkdtemp(prefix="v2_probe_")
SOURCE = os.path.join(HERE, "model_in.csv")
if not os.path.exists(SOURCE):
    i = pl.int_range(ROWS)
    pl.select(i.alias("id"), (i % 100).alias("kind"), (i % 50).alias("branch"), (i * 7 % 1000).alias("amount"),
              pl.format("T{}", i % 9973).alias("text")).write_csv(SOURCE)
LOOKUP = pl.LazyFrame({"branch": list(range(45)), "region": [f"R{n % 5}" for n in range(45)]})
COUNTS = {}


def counted(frame, name):
    def note(batch):
        COUNTS[name] = COUNTS.get(name, 0) + batch.height
        return batch
    return frame.map_batches(note, streamable=True, validate_output_schema=False, projection_pushdown=True,
                             predicate_pushdown=False, slice_pushdown=False)


def barrier(frame):
    """A node the optimizer cannot move anything through."""
    return frame.map_batches(lambda batch: batch, streamable=True, validate_output_schema=False,
                             projection_pushdown=False, predicate_pushdown=False, slice_pushdown=False)


def plans(share, out):
    """The six outputs of a job shaped like the payments scenario; ``share`` is put on every frame read twice."""
    read = counted(pl.scan_csv(SOURCE), "reader")
    flagged = share(read.with_columns((pl.col("kind") != 7).alias("__keep")))                  # filter rows
    main1 = counted(flagged.filter(pl.col("__keep")).drop("__keep"), "filter main")
    reject1 = flagged.filter(~pl.col("__keep")).drop("__keep")
    unique = counted(main1.unique(subset="id", keep="first", maintain_order=True), "unique")
    found = share(unique.join(LOOKUP, on="branch", how="left", maintain_order="left"))        # join
    main2 = counted(found.filter(pl.col("region").is_not_null()), "join main")
    reject2 = found.filter(pl.col("region").is_null()).drop("region")
    prepared = counted(main2.with_columns((pl.col("amount") * 2).alias("double")), "map 1")
    joined = share(prepared.with_columns(pl.col("text").str.to_lowercase().alias("low")))     # map 2, three outputs
    enriched = counted(joined.select("id", "region", "amount", "double", "low"), "map 2 out 1")
    high = joined.filter(pl.col("amount") > 900).select("id", "amount")
    cross = joined.filter(pl.col("kind") % 4 == 0).select("id", "kind", "low")
    ordered = share(enriched.sort("amount", "id", descending=[True, False], maintain_order=True))  # read by two
    totals = ordered.group_by("region", maintain_order=True).agg(pl.len().alias("n"), pl.col("amount").sum())
    frames = {"enriched": ordered, "high": high, "cross": cross, "totals": totals, "reject1": reject1, "reject2": reject2}
    return [frame.sink_csv(os.path.join(out, name + ".csv"), lazy=True) for name, frame in frames.items()]


def digest(out):
    found = hashlib.sha256()
    for name in sorted(os.listdir(out)):
        found.update(name.encode())
        found.update(open(os.path.join(out, name), "rb").read())
    return found.hexdigest()[:10]


WAYS = {
    "as today: nothing marked": lambda frame: frame,
    "cache() on every frame read twice": lambda frame: frame.cache(),
    "cache() and a barrier behind it": lambda frame: barrier(frame.cache()),
}
if __name__ == "__main__":
    for engine in ("streaming", "in-memory"):
        for label, share in WAYS.items():
            out = os.path.join(HERE, "out_" + str(abs(hash(label)) % 10**6))
            os.makedirs(out, exist_ok=True)
            COUNTS.clear()
            try:
                pl.collect_all(plans(share, out), engine=engine)
                runs = {name: round(count / ROWS, 2) for name, count in COUNTS.items()}
                print(f"{engine:10} {label:36} files {digest(out)}  times the source's rows passed: {runs}")
            except Exception as exc:
                print(f"{engine:10} {label:36} FAILS: {' '.join(str(exc).split())[:150]}")
    if "--explain" in sys.argv:
        print(pl.explain_all(plans(WAYS["as today: nothing marked"], HERE)))
