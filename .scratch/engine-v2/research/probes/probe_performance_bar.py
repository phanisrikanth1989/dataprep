"""Timings behind the answer in ../../issues/05-performance-bar.md.

For the hard cases that ticket names: what a config key costs against the
same job without it. Polars only; nothing from
src/ is imported. Run from the repo root:

    P=.scratch/engine-v2/research/probes/probe_performance_bar.py
    .venv/bin/python $P gen <dir> [rows]      write the data files (default 2,000,000 rows, about 1.2 GB in all)
    .venv/bin/python $P list                  print the variant names
    .venv/bin/python $P run <dir> <variant>   median of 5 runs on the in-memory engine, one JSON line
    .venv/bin/python $P trailer <dir>         footer routes on a trailer line that does not fit the schema

One variant runs per process, so the peak memory printed is that variant's.
Observations only: every result carries the machine and the Polars version,
and says nothing about another machine.
"""
import gc
import json
import os
import platform
import resource
import shutil
import statistics
import sys
import time

sys.dont_write_bytecode = True

import polars as pl  # noqa: E402

SEP = ";"
DEFAULT_ROWS = 2_000_000
RUNS = 5

ALL = ["id", "cust", "name", "city", "amount", "qty", "price", "active", "trade_date", "note"]
TYPED = {
    "id": pl.Int64, "cust": pl.String, "name": pl.String, "city": pl.String,
    "amount": pl.Float64, "qty": pl.Int64, "price": pl.Float64, "active": pl.Boolean,
    "trade_date": pl.String, "note": pl.String,
}
STRINGS = {c: pl.String for c in ALL}
CASTS = {"id": pl.Int64, "amount": pl.Float64, "qty": pl.Int64, "price": pl.Float64, "active": pl.Boolean}
DATE_FMT = "%Y-%m-%d"
E_ACUTE = chr(233)


def lenient(c, t):
    """Cast a String column leniently: a value that does not fit becomes null."""
    if t == pl.Boolean:  # Polars has no String -> Boolean cast
        return pl.when(pl.col(c) == "true").then(True).when(pl.col(c) == "false").then(False).otherwise(None)
    return pl.col(c).cast(t, strict=False)


def paths(d):
    return {k: os.path.join(d, k + ".csv") for k in ("clean", "dirty", "trailer", "accents_utf8", "latin", "lookup")}


# ---------------------------------------------------------------- data ----

def gen(d, n=DEFAULT_ROWS):
    import numpy as np

    os.makedirs(d, exist_ok=True)
    p = paths(d)
    rng = np.random.default_rng(42)
    raw = pl.DataFrame({
        "id": np.arange(n),
        "cust_n": rng.integers(0, 500_000, n),
        "upper": rng.random(n) < 0.3,
        "name_n": rng.integers(0, 1_000_000, n),
        "city_n": rng.integers(0, 20, n),
        "amount": np.round(rng.uniform(0, 10000, n), 2),
        "qty": rng.integers(1, 1000, n),
        "price": np.round(rng.uniform(0, 500, n), 4),
        "active": rng.random(n) < 0.66,
        "day": rng.integers(0, 3650, n),
        "note_n": rng.integers(0, 10**9, n),
    })
    cust_digits = pl.col("cust_n").cast(pl.String).str.zfill(6)
    df = raw.select(
        "id",
        pl.when("upper").then(pl.format("CUST_{}", cust_digits)).otherwise(pl.format("Cust_{}", cust_digits)).alias("cust"),
        pl.format("name_{}", "name_n").alias("name"),
        pl.format("city_{}", "city_n").alias("city"),
        "amount", "qty", "price", "active",
        (pl.date(2015, 1, 1) + pl.duration(days="day")).dt.strftime(DATE_FMT).alias("trade_date"),
        pl.format("note text number {} for this row", "note_n").alias("note"),
    )
    df.write_csv(p["clean"], separator=SEP)

    # 0.1% of qty and 0.1% of amount are not numbers.
    df.with_columns(
        pl.when(pl.col("id") % 1000 == 7).then(pl.lit("N/A")).otherwise(pl.col("qty").cast(pl.String)).alias("qty"),
        pl.when(pl.col("id") % 1000 == 13).then(pl.lit("n/a")).otherwise(pl.col("amount").cast(pl.String)).alias("amount"),
    ).write_csv(p["dirty"], separator=SEP)

    # A trailer record that does not fit the schema.
    shutil.copyfile(p["clean"], p["trailer"])
    with open(p["trailer"], "ab") as f:
        f.write(("TRAILER;%d\n" % n).encode())

    # The same file with an accent in every tenth name, in UTF-8 and ISO-8859-15.
    accented = pl.col("name").str.replace("name", "n" + E_ACUTE + "me")
    df.with_columns(
        pl.when(pl.col("id") % 10 == 0).then(accented).otherwise("name").alias("name")
    ).write_csv(p["accents_utf8"], separator=SEP)
    with open(p["accents_utf8"], "r", encoding="utf-8", newline="") as src, \
            open(p["latin"], "w", encoding="iso-8859-15", newline="") as dst:
        shutil.copyfileobj(src, dst, 1 << 24)

    # Lookup: 200,000 keys, two rows each.
    k = np.repeat(np.arange(200_000), 2)
    pl.DataFrame({"k": k, "seq": np.tile(np.array([1, 2]), 200_000)}).select(
        pl.format("Cust_{}", pl.col("k").cast(pl.String).str.zfill(6)).alias("cust"),
        pl.format("seg_{}", pl.col("k") % 7).alias("segment"),
        (pl.col("k") * 10 + pl.col("seq")).alias("credit_limit"),
    ).write_csv(p["lookup"], separator=SEP)

    for k_, v in p.items():
        print(k_, os.path.getsize(v), "bytes")


# --------------------------------------------------------- job shapes ----

def tail_full(lf):
    """The job uses every column."""
    return lf


def tail_narrow(lf):
    """The job filters to a tenth of the rows and uses three of ten columns."""
    return lf.filter(pl.col("amount") > 9000).select("id", "cust", "amount")


TAILS = {"full": tail_full, "narrow": tail_narrow}


def with_date(lf):
    return lf.with_columns(pl.col("trade_date").str.to_date(DATE_FMT))


def scan_typed(path, **kw):
    return pl.scan_csv(path, separator=SEP, schema_overrides=TYPED, **kw)


def scan_strings(path, **kw):
    return pl.scan_csv(path, separator=SEP, schema_overrides=STRINGS, **kw)


# ------------------------------------------------------------ sources ----

def base(p, shape):
    return lambda: TAILS[shape](with_date(scan_typed(p["clean"]))).collect()


def footer_eager(p, shape):
    """v2 as found: read the whole file eagerly, then drop the last row."""
    def run():
        df = pl.read_csv(p["clean"], separator=SEP, schema_overrides=TYPED)
        df = df.head(len(df) - 1)
        return TAILS[shape](with_date(df.lazy())).collect()
    return run


def footer_two_pass(p, shape):
    """Count the rows with one lazy pass, then scan with n_rows."""
    def run():
        n = scan_typed(p["clean"]).select(pl.len()).collect().item()
        return TAILS[shape](with_date(scan_typed(p["clean"], n_rows=n - 1))).collect()
    return run


def footer_in_plan(p, shape):
    """One plan: keep rows whose position is before the last one."""
    def run():
        lf = scan_typed(p["clean"]).filter(pl.int_range(pl.len()) < pl.len() - 1)
        return TAILS[shape](with_date(lf)).collect()
    return run


def footer_count_in_plan(p, shape):
    """One plan: the row count is a second scan inside the plan, joined on."""
    def run():
        n = scan_typed(p["clean"]).select(pl.len().alias("__n"))
        lf = scan_typed(p["clean"]).with_row_index("__i").join(n, how="cross")
        lf = lf.filter(pl.col("__i") < pl.col("__n") - 1).drop("__i", "__n")
        return TAILS[shape](with_date(lf)).collect()
    return run


def encoding_base(p, shape):
    return lambda: TAILS[shape](with_date(scan_typed(p["accents_utf8"]))).collect()


def encoding_eager(p, shape):
    """The only route Polars has for ISO-8859-15: eager, decoded in Python."""
    def run():
        df = pl.read_csv(p["latin"], separator=SEP, schema_overrides=TYPED, encoding="iso-8859-15")
        return TAILS[shape](with_date(df.lazy())).collect()
    return run


def _is_ascii(path, chunk=1 << 24):
    with open(path, "rb", buffering=0) as f:
        while True:
            b = f.read(chunk)
            if not b:
                return True
            if not b.isascii():
                return False


def ascii_check(p, shape):
    """Check every byte is ASCII (one pass, in C, outside Polars), then scan lazily."""
    def run():
        assert _is_ascii(p["clean"])
        return TAILS[shape](with_date(scan_typed(p["clean"]))).collect()
    return run


# ---- die_on_error: false at a source ----

def _as_found_validate(df):
    """SourceComponent._validate_schema from v2 as found, minus config plumbing.

    One change: the Boolean column goes through lenient(), because the cast the
    component uses fails (see probe_performance_bar_engines.py as-found).
    """
    cast_cols = list(CASTS) + ["trade_date"]
    pre = {c: df[c].is_null() for c in cast_cols}
    exprs = [lenient(c, t).alias(c) for c, t in CASTS.items()]
    exprs.append(pl.col("trade_date").str.to_date(DATE_FMT, strict=False).alias("trade_date"))
    cast = df.with_columns(exprs)
    mask = pl.Series("_has_error", [False] * len(cast))
    for c in cast_cols:
        new_nulls = cast[c].is_null() & ~pre[c]
        if new_nulls.any():
            mask = mask | new_nulls
    if not mask.any():
        return cast.lazy(), None
    good = cast.filter(~mask)
    bad = df.filter(mask)
    msgs = []
    for i in mask.arg_true():
        failed = [c for c in cast_cols if cast[c].is_null()[i] and not pre[c][i]]
        msgs.append("Schema cast failed: " + ", ".join(failed))
    bad = bad.with_columns(pl.Series("_error_message", msgs))
    return good.lazy(), bad.lazy()


def doe_as_found(p, shape, file):
    """v2 as found: read strings, collect at the source, validate eagerly."""
    def run():
        df = scan_strings(p[file], ignore_errors=True).collect()
        main, reject = _as_found_validate(df)
        out = TAILS[shape](main).collect()
        rej = reject.collect() if reject is not None else None
        return out, rej
    return run


def lazy_validate(path):
    """The same split built from lazy expressions: returns (main, reject)."""
    cast_cols = list(CASTS) + ["trade_date"]
    lf = scan_strings(path)
    casts = [lenient(c, t).alias("__c_" + c) for c, t in CASTS.items()]
    casts.append(pl.col("trade_date").str.to_date(DATE_FMT, strict=False).alias("__c_trade_date"))
    failed = {c: pl.col("__c_" + c).is_null() & pl.col(c).is_not_null() for c in cast_cols}
    lf = lf.with_columns(casts).with_columns(pl.any_horizontal(list(failed.values())).alias("__bad"))
    main = lf.filter(~pl.col("__bad")).select(
        [(pl.col("__c_" + c).alias(c) if c in cast_cols else pl.col(c)) for c in ALL]
    )
    message = pl.concat_str(
        [pl.lit("Schema cast failed:")] + [pl.when(e).then(pl.lit(" " + c)).otherwise(pl.lit("")) for c, e in failed.items()]
    )
    reject = lf.filter(pl.col("__bad")).select(ALL + [message.alias("_error_message")])
    return main, reject


def doe_lazy_main(p, shape, file):
    """Stay lazy: read strings, cast leniently, drop bad rows. No reject output wired."""
    def run():
        main, _ = lazy_validate(p[file])
        return TAILS[shape](main).collect()
    return run


def doe_lazy_both(p, shape, file):
    """Stay lazy, reject output wired: main and reject collected as one plan."""
    def run():
        main, reject = lazy_validate(p[file])
        return pl.collect_all([TAILS[shape](main), reject])
    return run


# --------------------------------------------------------- transforms ----
# Timed on a frame already in memory, so the ratio is the component's own.

def _mem(p):
    return pl.read_csv(p["clean"], separator=SEP, schema_overrides=TYPED)


def uniq(p, case_insensitive, keep, order):
    df = _mem(p)

    def run():
        lf = df.lazy()
        key = "cust"
        if case_insensitive:
            lf = lf.with_columns(pl.col("cust").str.to_lowercase().alias("__k"))
            key = "__k"
        lf = lf.unique(subset=[key], keep=keep, maintain_order=order)
        if case_insensitive:
            lf = lf.drop("__k")
        return lf.collect()
    return run


def group(p, order):
    df = _mem(p)
    return lambda: df.lazy().group_by("cust", maintain_order=order).agg(pl.col("amount").sum(), pl.len()).collect()


def join(p, mode, order):
    df = _mem(p)
    lk = pl.read_csv(p["lookup"], separator=SEP)

    def run():
        right = lk.lazy()
        if mode == "last":
            right = right.unique(subset=["cust"], keep="last", maintain_order=True)
        elif mode == "first":
            right = right.unique(subset=["cust"], keep="first", maintain_order=True)
        return df.lazy().join(right, on="cust", how="left", maintain_order=("left" if order else "none")).collect()
    return run


def variants(p):
    v = {}
    for s in ("full", "narrow"):
        v[f"base.{s}"] = base(p, s)
        v[f"footer_eager.{s}"] = footer_eager(p, s)
        v[f"footer_two_pass.{s}"] = footer_two_pass(p, s)
        v[f"footer_in_plan.{s}"] = footer_in_plan(p, s)
        v[f"footer_count_in_plan.{s}"] = footer_count_in_plan(p, s)
        v[f"encoding_base.{s}"] = encoding_base(p, s)
        v[f"encoding_eager.{s}"] = encoding_eager(p, s)
        v[f"ascii_check.{s}"] = ascii_check(p, s)
        for f in ("clean", "dirty"):
            v[f"doe_as_found.{f}.{s}"] = doe_as_found(p, s, f)
            v[f"doe_lazy_main.{f}.{s}"] = doe_lazy_main(p, s, f)
            v[f"doe_lazy_both.{f}.{s}"] = doe_lazy_both(p, s, f)
    v["uniq.sensitive.first_ordered"] = lambda: uniq(p, False, "first", True)
    v["uniq.insensitive.first_ordered"] = lambda: uniq(p, True, "first", True)
    v["uniq.sensitive.any_unordered"] = lambda: uniq(p, False, "any", False)
    v["uniq.insensitive.any_unordered"] = lambda: uniq(p, True, "any", False)
    v["group.unordered"] = lambda: group(p, False)
    v["group.ordered"] = lambda: group(p, True)
    for mode in ("all", "last", "first"):
        v[f"join.{mode}.unordered"] = (lambda m=mode: join(p, m, False))
        v[f"join.{mode}.ordered"] = (lambda m=mode: join(p, m, True))
    return v


PREPARED = ("uniq.", "group.", "join.")


def shape_of(out):
    if out is None:
        return None
    if isinstance(out, (list, tuple)):
        return [shape_of(o) for o in out]
    return list(out.shape)


def peak_rss_mb():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round((rss if sys.platform == "darwin" else rss * 1024) / 1e6)


def run(d, name):
    p = paths(d)
    fn = variants(p)[name]
    if name.startswith(PREPARED):
        fn = fn()  # builds the in-memory input, outside the timing
    out = fn()  # warm-up
    times = []
    for _ in range(RUNS):
        del out
        gc.collect()
        t0 = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t0)
    print(json.dumps({
        "variant": name,
        "median_s": round(statistics.median(times), 4),
        "min_s": round(min(times), 4),
        "max_s": round(max(times), 4),
        "peak_rss_mb": peak_rss_mb(),
        "out": shape_of(out),
        "runs": RUNS,
        "input_mb": round(os.path.getsize(p["clean"]) / 1e6),
        "polars": pl.__version__,
        "python": platform.python_version(),
        "machine": platform.machine() + " " + platform.system(),
        "cpus": os.cpu_count(),
    }))


# ------------------------------------------------------------ trailer ----

def trailer(d):
    """Drop a one-line trailer that does not fit the schema, six ways."""
    t = paths(d)["trailer"]

    def cast_all(lf):
        return lf.with_columns([lenient(c, ty).alias(c) for c, ty in CASTS.items()])

    def count_typed():
        return scan_typed(t).select(pl.len()).collect().item()

    def two_pass_typed():
        return scan_typed(t, n_rows=count_typed() - 1).collect().shape

    def in_plan_typed():
        return scan_typed(t).filter(pl.int_range(pl.len()) < pl.len() - 1).collect().shape

    def eager_typed():
        df = pl.read_csv(t, separator=SEP, schema_overrides=TYPED)
        return df.head(len(df) - 1).shape

    def two_pass_strings():
        n = scan_strings(t).select(pl.len()).collect().item()
        df = cast_all(scan_strings(t, n_rows=n - 1)).collect()
        return df.shape, "null ids: %d" % df["id"].null_count()

    def in_plan_strings():
        df = cast_all(scan_strings(t).filter(pl.int_range(pl.len()) < pl.len() - 1)).collect()
        return df.shape, "null ids: %d" % df["id"].null_count()

    checks = [
        ("count the rows, typed read", count_typed),
        ("typed read, count first then row limit", two_pass_typed),
        ("typed read, position filter in the plan", in_plan_typed),
        ("typed read, eager then head", eager_typed),
        ("text read, count first, then convert", two_pass_strings),
        ("text read, position filter, then convert", in_plan_strings),
    ]
    for label, fn in checks:
        try:
            print(f"{label:42s} OK   {fn()}")
        except Exception as e:  # the failure text is the finding
            print(f"{label:42s} FAIL {type(e).__name__}: {str(e).splitlines()[0][:100]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "gen":
        gen(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_ROWS)
    elif cmd == "list":
        print("\n".join(variants(paths("."))))
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3])
    elif cmd == "trailer":
        trailer(sys.argv[2])
    else:
        raise SystemExit(__doc__)
