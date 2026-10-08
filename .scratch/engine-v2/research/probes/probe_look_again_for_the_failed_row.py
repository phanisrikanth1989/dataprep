"""Try-out for ticket 38: after a map expression fails on one row, find that row by looking again.

Run, from the repository's root:

    .venv/bin/python -c "from pathlib import Path; from scenarios.payments import data; data.generate(Path('WORK/data'), 1000000)"
    .venv/bin/python .scratch/engine-v2/research/probes/probe_look_again_for_the_failed_row.py WORK 654321

A bad value is planted in one data row of the payments file, in a column a
map converts with int(). The job fails as it does today: Polars names the
value and no row. Then the blamed component's own part of the plan is run
again on a window of the reader's rows, the window halved each time, until
one row is left. The window is cut right after the scan, so Polars skips to
it by counting lines.

Observed 2026-10-06, polars 1.44.2, Apple M4 (10 cores, 16 GB), warm file
cache, 45 columns of about 470 bytes a row:

    1,000,000 rows (0.47 GB), bad row 654,321:   23 runs,  2.1 s
    5,000,000 rows (2.3 GB),  bad row 4,321,000: 26 runs, 13.1 s

Both times the row found was the planted one, and its place plus the header
line is the line an editor shows. The crude form tried for ticket 37 (the
whole job rerun, every output written) took 50 s for the first case.

Skipping costs about 0.06 s for 0.47 GB here, so the time grows with the
size of the file; a file of 100 GB wants a limit on how long the search may
take. The files it writes land under WORK.
"""
import sys
import time
from pathlib import Path

import polars as pl

sys.path.insert(0, ".")
from scenarios.payments import jobs  # noqa: E402
from src.v2 import load_job  # noqa: E402
from src.v2.components.file.file_input_delimited import FileInputDelimited  # noqa: E402
from src.v2.engine.runner import Runner, _Failed, _Subjob  # noqa: E402
from src.v2.job.graph import subjobs  # noqa: E402

work, planted = Path(sys.argv[1]), int(sys.argv[2])
source, bad = work / "data" / "payments.csv", work / "data_bad"
bad.mkdir(exist_ok=True)
for name in ("branches.csv", "customers.csv", "purposes.csv", "settings.csv"):
    if not (bad / name).exists():
        (bad / name).write_bytes((work / "data" / name).read_bytes())

# ---- plant: data row `planted` (1 is the first row under the header) gets an operator id int() cannot read ----
started = time.perf_counter()
with open(source, "rb") as old, open(bad / "payments.csv", "wb") as new:
    header = old.readline()
    place = header.rstrip(b"\n").split(b";").index(b"operator_id")
    new.write(header)
    for number, line in enumerate(old, start=1):
        if number == planted:
            fields = line.rstrip(b"\n").split(b";")
            fields[place] = b"OPx320"
            line = b";".join(fields) + b"\n"
        new.write(line)
print(f"planted OPx320 in data row {planted:,} (file line {planted + 1:,}) of {number:,}; {time.perf_counter() - started:.1f} s")

made = jobs.build("python", bad, work / "out_bad")
(work / "out_bad").mkdir(exist_ok=True)
by_id = {component["id"]: component for component in made["components"]}
column = next(c for c in by_id["prepare"]["config"]["outputs"][0]["columns"] if c["name"] == "customer_id")
column["expression"] = "joined.customer_id + int(joined.operator_id[2:]) * 0"
job = load_job(made)

# ---- the job as it fails today ----
started = time.perf_counter()
result = Runner(job).run()
print(f"\nthe job today: {result.status} at {result.failed_component} after {time.perf_counter() - started:.1f} s")
print("  ", result.error[:150])

# ---- look again ----
WINDOW = {}
plain_fields = FileInputDelimited._fields


def windowed(self, source_path, names, native):
    frame = plain_fields(self, source_path, names, native)
    if self.id in WINDOW:
        first, count = WINDOW[self.id]
        frame = frame.slice(first, count)
    return frame


FileInputDelimited._fields = windowed
blamed = result.failed_component
members = next(group for group in subjobs(job) if blamed in group)
upto = members[: members.index(blamed) + 1]
runs = 0


def fails(reader, first, count):
    """Whether the blamed component still fails when one reader hands on only a window of its rows."""
    global runs
    runs += 1
    WINDOW.clear()
    WINDOW[reader] = (first, count)
    runner = Runner(job)
    runner.run_context.fast_read = False
    # What the settings subjob loaded into the context, which this subjob reads.
    runner.run_context.context.update(result.context)
    state = _Subjob()
    try:
        runner._build(upto, state)
        frames = [frame for component_id, frame in state.produced if component_id == blamed]
        pl.collect_all([frame.select(pl.all().count()) for frame in frames], engine=runner.engine)
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, _Failed) and exc.component_id != blamed:
            raise
        return True
    finally:
        runner.run_context.cleanup()
    return False


started = time.perf_counter()
reader = "payments_in"
total = pl.scan_csv(str(bad / "payments.csv"), separator=";", has_header=False, skip_rows=1,
                    quote_char=None, truncate_ragged_lines=True, glob=False,
                    schema={"line": pl.String}).select(pl.len()).collect().item()
print(f"\nrows of {reader}: {total:,}")
assert fails(reader, 0, total), "the failure does not come back"
assert not fails(reader, 0, 0), "the failure does not depend on this reader's rows"
low, high = 0, total
while high - low > 1:
    middle = (low + high) // 2
    if fails(reader, low, middle - low):
        high = middle
    else:
        low = middle
took = time.perf_counter() - started
assert fails(reader, low, 1), "the row found does not fail alone"
header_rows = by_id[reader]["config"].get("header_rows", 0)
print(f"found: record {low + 1:,} of {reader}, line {low + 1 + header_rows:,} of the file, in {runs} runs and {took:.1f} s")
with open(bad / "payments.csv", encoding="utf-8") as handle:
    for number, line in enumerate(handle, start=1):
        if number == low + 1 + header_rows:
            break
print("that line starts:", line[:60].strip(), "... operator_id =", line.rstrip().split(";")[place])
