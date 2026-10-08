"""Polars 1.44.2: the number of rows of a cut union comes out wrong.

Run: .venv/bin/python .scratch/engine-v2/research/probes/probe_polars_count_of_a_cut_union.py

Observed 2026-10-06 on polars 1.44.2 (macOS arm64), both the streaming and
the in-memory engine. Frames put one after another (`concat`) and then cut
(`slice`, `head`): asked for the number of rows outright
(`select(pl.len())`), Polars counts each frame on its own and cuts the list
of counts instead of the rows. Five rows less the first two come out as 0;
the first three of five come out as 4. Collected and measured, the same
frame is right. The plan says it: SELECT [len()] sits inside each PLAN of
the SLICED UNION.

Found through v2's full-row input, which puts one empty line after the
lines of a file that ends in a line end and then skips the header.

Each case prints OK or WRONG.

Consequence for v2: the engine counts rows by numbering them and taking the
highest number (`_row_count` in src/v2/engine/runner.py).
"""
import polars as pl

NUMBER = "__n"


def cut(offset, length):
    return pl.concat([pl.LazyFrame({"n": [1, 2, 3, 4]}), pl.LazyFrame({"n": [0]})]).slice(offset, length)


WAYS = {
    "select(pl.len())": lambda frame: frame.select(pl.len()),
    "select(pl.first().len())": lambda frame: frame.select(pl.first().len()),
    "rows numbered, highest + 1": lambda frame: frame.with_row_index(NUMBER).select(
        (pl.col(NUMBER).max().cast(pl.Int64) + 1).fill_null(0)
    ),
}

for name, way in WAYS.items():
    for offset, length, rows in ((2, None, 3), (2, 2, 2), (0, 3, 3), (0, None, 5)):
        for engine in ("streaming", "in-memory"):
            found = way(cut(offset, length)).collect(engine=engine).item()
            held = cut(offset, length).collect(engine=engine).height
            mark = "OK   " if found == rows == held else "WRONG"
            print(f"{mark} {name:28s} slice({offset}, {length}) {engine:10s} counted {found}, holds {held}")

print()
print(cut(2, None).select(pl.len()).explain())
