"""Try-out for ticket 38: a row number that travels with the row, and a conversion checked by the engine.

Run, from the repository's root:

    .venv/bin/python -c "from pathlib import Path; from scenarios.payments import data; data.generate(Path('WORK/data'), 1000000)"
    .venv/bin/python .scratch/engine-v2/research/probes/probe_row_number_and_checked_conversion.py WORK

The dev's idea (2026-10-07): give every row of a source a number as it is
read, let it travel with the row, and name it when the row fails. Polars
says which value failed and never which row, so the number is of use only
where the engine holds the failing row itself. This puts the two together
for a conversion in an expression, int(operator_id[2:]):

- as v2 builds it today, a strict cast: Polars raises on the first bad value;
- checked by the engine: the cast is made without raising, a row whose text
  was there and gave no number is flagged, and one more small plan in the
  same pass asks how many rows are flagged, the lowest row number among
  them, and that row's value and key.

Two rows of the payments file are spoiled: row 654,321 (OPx320) and row
800,000 (blanks).

Observed 2026-10-07, polars 1.44.2, Apple M4, 1,000,000 rows of 45 columns,
best of three, streaming engine, the 21 columns of the job's map written:

    clean file, conversion as today      0.17 s  ok
    clean file, checked by the engine    0.17 s  0 rows flagged
    bad rows,   conversion as today      0.17 s  Polars: ... failed in column 'operator_id' for 1 out of 1098 values: ["x320"]
    bad rows,   checked by the engine    0.17 s  2 rows, first 654321, value 'OPx320', key '654321'

So the check costs nothing that shows, and it gives the count, the first
row's number, the cell as it stands in the file and the row's key in the
pass that would have failed anyway.

Measured beside it with a throwaway change to the payments scenario's job
(one more whole-number column read from the file, passed through both maps
and written to every output, which is more than a hidden column costs):
1.87 s without, 1.89 s with, 1.85 s without again.
"""
import sys
import time
from pathlib import Path

import polars as pl

work = Path(sys.argv[1])
clean, spoiled = work / "data" / "payments.csv", work / "spoiled.csv"
with open(clean, "rb") as old, open(spoiled, "wb") as new:
    header = old.readline()
    new.write(header)
    names = header.decode().strip().split(";")
    place = names.index("operator_id")
    for number, line in enumerate(old, start=1):
        if number in (654321, 800000):
            fields = line.rstrip(b"\n").split(b";")
            fields[place] = b"OPx320" if number == 654321 else b"OP  "
            line = b";".join(fields) + b"\n"
        new.write(line)

NUMBER = "__v2_row"


def plans(path, checked):
    """scan -> filter -> one converted column -> write 21 columns; with the check beside it when asked."""
    rows = pl.scan_csv(str(path), separator=";", has_header=False, skip_rows=1, schema={n: pl.String for n in names},
                       quote_char=None, encoding="utf8-lossy", truncate_ragged_lines=True, glob=False,
                       row_index_name=NUMBER, row_index_offset=1)
    rows = rows.filter(pl.col("currency").str.contains("^[A-Z]{3}$"))
    text = pl.col("operator_id").str.slice(2).str.strip_chars()
    if checked:
        number = text.cast(pl.Int64, strict=False)
        failed = text.is_not_null() & number.is_null()
    else:
        number, failed = text.cast(pl.Int64), None
    out = rows.with_columns((pl.col("customer_id").cast(pl.Int64) + number * 0).alias("customer_id")).select(names[:21])
    made = [out.sink_csv(str(work / "written.csv"), separator=";", lazy=True)]
    if checked:
        made.append(rows.filter(failed).select(
            pl.len().alias("rows"), pl.col(NUMBER).min().alias("first"),
            pl.col("operator_id").sort_by(NUMBER).first().alias("value"),
            pl.col("txn_id").sort_by(NUMBER).first().alias("key"),
        ))
    return made


def run(label, path, checked):
    best, said = None, ""
    for _ in range(3):
        started = time.perf_counter()
        try:
            got = pl.collect_all(plans(path, checked), engine="streaming")
            said = "ok" if not checked else str(got[1].row(0, named=True))
        except Exception as exc:  # noqa: BLE001
            said = "Polars: " + " ".join(str(exc).split())[:100]
        took = time.perf_counter() - started
        best = took if best is None else min(best, took)
    print(f"{label:38s} {best:5.2f} s  {said}")


run("clean file, conversion as today", clean, False)
run("clean file, checked by the engine", clean, True)
run("bad rows,   conversion as today", spoiled, False)
run("bad rows,   checked by the engine", spoiled, True)
