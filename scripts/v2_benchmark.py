"""Time the v2 engine on a generated file, next to hand-written Polars.

    .venv/bin/python scripts/v2_benchmark.py [--mb 500] [--only copy,sort] [--keep] [--v1]

For each scenario the same work is done twice: by a v1-shaped job config run
on v2, and by a few lines of Polars written for the purpose, with native
types and none of v1's rules (no rejected rows, no blank-tolerant numbers).
The second is the floor: what Polars costs when it has to promise nothing.
Where both write the same thing, the two files are compared byte for byte.

``--v1`` also runs each job on the v1 engine, for the speed-up. v1 holds the
whole file in memory as pandas; use a small ``--mb`` with it.

The input is generated at run time in a scratch folder and removed
afterwards (``--keep`` leaves it). Nothing here is committed or read by the
test suite.
"""
from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from src.v2 import run_job  # noqa: E402
from src.v2.components.registry import REGISTRY  # noqa: E402

COLUMNS = [
    ("id", "int"), ("account", "int"), ("name", "str"), ("dept", "str"), ("city", "str"),
    ("amount", "float"), ("rate", "float"), ("qty", "int"), ("balance", "float"), ("day", "datetime"),
]
NATIVE = {"int": pl.Int64, "float": pl.Float64, "str": pl.String, "datetime": pl.String}
DEPTS = ["Engineering", "Sales", "Marketing", "Finance", "Operations", "Legal", "HR", "Support"]
CITIES = ["New York", "London", "Singapore", "Mumbai", "Tokyo", "Frankfurt", "Sydney", "Toronto", "Dublin", "Zurich"]
ROWS_PER_MB = 11300


# ------------------------------------------------------------------
# Data
# ------------------------------------------------------------------

def generate(folder: Path, megabytes: float, seed: int = 7) -> int:
    """Write big.csv (about the asked size), dirty.csv (1 in 100 rows unreadable) and two small lookups."""
    rows = int(megabytes * ROWS_PER_MB)
    rng = np.random.default_rng(seed)
    frame = pl.DataFrame({
        "id": np.arange(1, rows + 1),
        "account": rng.integers(10_000_000, 10_000_000 + max(rows // 2, 10), rows),
        "name": pl.Series(rng.integers(0, 10**9, rows)).cast(pl.String).str.zfill(9),
        "dept": np.array(DEPTS)[rng.integers(0, len(DEPTS), rows)],
        "city": np.array(CITIES)[rng.integers(0, len(CITIES), rows)],
        "amount": np.round(rng.uniform(1, 250000, rows), 2),
        "rate": np.round(rng.uniform(0.01, 0.2, rows), 4),
        "qty": rng.integers(1, 5000, rows),
        "balance": np.round(rng.normal(50000, 20000, rows), 2),
        "day": rng.integers(0, 3650, rows),
    }).with_columns(
        name=pl.lit("cust_") + pl.col("name"),
        day=(pl.date(2015, 1, 1) + pl.duration(days=pl.col("day"))).dt.strftime("%Y-%m-%d"),
    )
    frame.write_csv(folder / "big.csv", separator=";", quote_style="never")
    dirty = frame.with_columns(
        pl.when(pl.col("id") % 100 == 0).then(pl.lit("n/a")).otherwise(pl.col("qty").cast(pl.String)).alias("qty")
    )
    dirty.write_csv(folder / "dirty.csv", separator=";", quote_style="never")
    pl.DataFrame({"city": CITIES, "region": ["AMER", "EMEA", "APAC", "APAC", "APAC", "EMEA", "APAC", "AMER", "EMEA", "EMEA"]}
                 ).write_csv(folder / "cities.csv", separator=";", quote_style="never")
    pl.DataFrame({"dept": DEPTS, "head": [f"head_{index}" for index in range(len(DEPTS))]}
                 ).write_csv(folder / "depts.csv", separator=";", quote_style="never")
    return rows


# ------------------------------------------------------------------
# Job configs, in v1's shape
# ------------------------------------------------------------------

def schema(columns: List[Any] = COLUMNS) -> List[Dict[str, Any]]:
    made = []
    for name, type_name in columns:
        column = {"name": name, "type": type_name, "nullable": True, "key": False}
        if type_name == "datetime":
            column["date_pattern"] = "%Y-%m-%d"
        made.append(column)
    return made


def reader(component_id: str = "in", path: str = "big.csv", columns: List[Any] = COLUMNS, outputs=("row1",)) -> Dict[str, Any]:
    config = {"filepath": path, "fieldseparator": ";", "row_separator": "\\n", "header_rows": 1,
              "encoding": "ISO-8859-15", "die_on_error": False, "remove_empty_row": True}
    return {"id": component_id, "type": "FileInputDelimited", "config": config,
            "schema": {"input": [], "output": schema(columns)}, "inputs": [], "outputs": list(outputs)}


def writer(flow_name: str, columns: List[Any] = COLUMNS, component_id: str = "out", path: str = "out_v2.csv") -> Dict[str, Any]:
    config = {"filepath": path, "fieldseparator": ";", "encoding": "ISO-8859-15", "include_header": True,
              "file_exist_exception": False}
    return {"id": component_id, "type": "FileOutputDelimited", "config": config,
            "schema": {"input": schema(columns), "output": []}, "inputs": [flow_name], "outputs": []}


def flow(name: str, source: str, target: str, kind: str = "flow") -> Dict[str, str]:
    return {"name": name, "from": source, "to": target, "type": kind}


def job(components: List[Dict[str, Any]], flows: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"job_name": "bench", "default_context": "Default", "context": {"Default": {}},
            "components": components, "flows": flows, "triggers": [], "java_config": {"enabled": False}}


def through(component_type: str, config: Dict[str, Any], out_columns: List[Any] = COLUMNS, out_kind: str = "flow",
            in_schema: Optional[List[Any]] = None) -> Dict[str, Any]:
    """big.csv -> one component -> out_v2.csv."""
    middle = {"id": "it", "type": component_type, "config": config,
              "schema": {"input": schema(in_schema or COLUMNS), "output": schema(out_columns)},
              "inputs": ["row1"], "outputs": ["row2"]}
    return job([reader(), middle, writer("row2", out_columns)],
               [flow("row1", "in", "it"), flow("row2", "it", "out", out_kind)])


# ------------------------------------------------------------------
# The same work, hand-written
# ------------------------------------------------------------------

def scan(path: str = "big.csv", columns: List[Any] = COLUMNS) -> pl.LazyFrame:
    frame = pl.scan_csv(path, separator=";", has_header=False, skip_rows=1, quote_char=None,
                        schema={name: NATIVE[type_name] for name, type_name in columns})
    if any(name == "day" for name, _ in columns):
        frame = frame.with_columns(pl.col("day").str.strptime(pl.Datetime("us"), "%Y-%m-%d"))
    return frame


def sink(frame: pl.LazyFrame) -> None:
    frame.sink_csv("out_hand.csv", separator=";", quote_style="never", datetime_format="%Y-%m-%d", engine="streaming")


# ------------------------------------------------------------------
# Scenarios
# ------------------------------------------------------------------

class Scenario:
    def __init__(self, name: str, needs: List[str], job_config: Callable[[], Dict[str, Any]],
                 by_hand: Callable[[], None], same_bytes: bool = True, v1_job: Optional[Callable[[], Dict[str, Any]]] = None) -> None:
        self.name, self.needs, self.job_config, self.by_hand = name, needs, job_config, by_hand
        self.same_bytes, self.v1_job = same_bytes, v1_job


AGG_OUT = [("dept", "str"), ("city", "str"), ("total", "float"), ("rows", "int"), ("avg_rate", "float"),
           ("low", "float"), ("high", "float")]
JOIN_OUT = COLUMNS + [("region", "str")]
MAP_OUT = [("id", "int"), ("label", "str"), ("net", "float"), ("head", "str")]
KEEP_OUT = [("id", "int"), ("dept", "str"), ("amount", "float"), ("day", "datetime")]
CITY, DEPT = [("city", "str"), ("region", "str")], [("dept", "str"), ("head", "str")]


def map_job(component_type: str) -> Dict[str, Any]:
    lookup = {"name": "row2", "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE", "filter": "",
              "activate_filter": False, "join_mode": "LEFT_OUTER_JOIN",
              "join_keys": [{"lookup_column": "dept", "expression": "row1.dept", "type": "str", "nullable": True, "operator": "="}]}
    columns = [("id", "row1.id", "int"), ("label", "row1.dept.upper() + '-' + row1.city", "str"),
               ("net", "row1.amount * (1 - row1.rate)", "float"), ("head", "row2.head", "str")]
    config = {
        "inputs": {"main": {"name": "row1", "filter": "", "activate_filter": False, "matching_mode": "UNIQUE_MATCH",
                            "lookup_mode": "LOAD_ONCE"}, "lookups": [lookup]},
        "variables": [],
        "outputs": [{"name": "out1", "is_reject": False, "inner_join_reject": False, "filter": "row1.qty > 100",
                     "activate_filter": True,
                     "columns": [{"name": name, "expression": expression, "type": type_name, "nullable": True}
                                 for name, expression, type_name in columns]}],
        "die_on_error": True,
    }
    middle = {"id": "it", "type": component_type, "config": config,
              "schema": {"input": schema(), "output": schema(MAP_OUT)}, "inputs": ["row1", "row2"], "outputs": ["out1"]}
    return job([reader(), reader("look", "depts.csv", DEPT, ("row2",)), middle, writer("out1", MAP_OUT)],
               [flow("row1", "in", "it"), flow("row2", "look", "it"), flow("out1", "it", "out")])


def join_job() -> Dict[str, Any]:
    config = {"use_inner_join": False, "join_key": [{"input_column": "city", "lookup_column": "city"}],
              "use_lookup_cols": True, "lookup_cols": [{"output_column": "region", "lookup_column": "region"}]}
    middle = {"id": "it", "type": "Join", "config": config,
              "schema": {"input": schema(), "output": schema(JOIN_OUT)}, "inputs": ["row1", "row2"], "outputs": ["row3"]}
    return job([reader(), reader("look", "cities.csv", CITY, ("row2",)), middle, writer("row3", JOIN_OUT)],
               [flow("row1", "in", "it"), flow("row2", "look", "it"), flow("row3", "it", "out")])


def reject_job() -> Dict[str, Any]:
    source = reader(path="dirty.csv", outputs=("row1", "bad"))
    return job([source, writer("row1"), writer("bad", [], "rej", "rej_v2.csv")],
               [flow("row1", "in", "out"), flow("bad", "in", "rej", "reject")])


def hand_map() -> None:
    lookup = scan("depts.csv", DEPT)
    frame = scan().filter(pl.col("qty") > 100).join(lookup, on="dept", how="left", maintain_order="left")
    sink(frame.select(
        "id", (pl.col("dept").str.to_uppercase() + "-" + pl.col("city")).alias("label"),
        (pl.col("amount") * (1 - pl.col("rate"))).alias("net"), "head",
    ))


def hand_aggregate() -> None:
    sink(scan().group_by(["dept", "city"], maintain_order=True).agg(
        pl.col("amount").sum().alias("total"), pl.len().alias("rows"), pl.col("rate").mean().alias("avg_rate"),
        pl.col("balance").min().alias("low"), pl.col("balance").max().alias("high"),
    ))


def hand_reject() -> None:
    text = dict(COLUMNS, qty="str")
    frame = scan("dirty.csv", list(text.items())).with_columns(pl.col("qty").cast(pl.Int64, strict=False).alias("__qty"))
    good = frame.filter(pl.col("__qty").is_not_null()).with_columns(pl.col("__qty").alias("qty")).drop("__qty")
    bad = frame.filter(pl.col("__qty").is_null()).drop("__qty")
    pl.collect_all([
        good.sink_csv("out_hand.csv", separator=";", quote_style="never", datetime_format="%Y-%m-%d", lazy=True),
        bad.sink_csv("rej_hand.csv", separator=";", quote_style="never", datetime_format="%Y-%m-%d", lazy=True),
    ], engine="streaming")


AGG_CONFIG = {
    "groupbys": [{"output_column": "dept", "input_column": "dept"}, {"output_column": "city", "input_column": "city"}],
    "operations": [
        {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
        {"output_column": "rows", "function": "count", "input_column": "amount", "ignore_null": True},
        {"output_column": "avg_rate", "function": "avg", "input_column": "rate", "ignore_null": True},
        {"output_column": "low", "function": "min", "input_column": "balance", "ignore_null": True},
        {"output_column": "high", "function": "max", "input_column": "balance", "ignore_null": True},
    ],
}
FILTER = [{"column": "amount", "operator": ">=", "value": "125000", "function": ""},
          {"column": "dept", "operator": "==", "value": "Sales", "function": ""}]
SORT = [{"column": "dept", "sort_type": "alpha", "order": "asc"}, {"column": "amount", "sort_type": "num", "order": "desc"}]
WANTED = (pl.col("amount") >= 125000) & (pl.col("dept") == "Sales")

SCENARIOS = [
    Scenario("copy", [], lambda: job([reader(), writer("row1")], [flow("row1", "in", "out")]), lambda: sink(scan())),
    Scenario("filter (conditions)", ["FilterRows"],
             lambda: through("FilterRows", {"logical_op": "&&", "conditions": FILTER}, out_kind="filter"),
             lambda: sink(scan().filter(WANTED))),
    Scenario("filter (expression)", ["FilterRows"],
             lambda: through("FilterRows", {"use_advanced": True, "conditions": [],
                                            "advanced_cond": "row1.amount >= 125000 and row1.dept == 'Sales'"}, out_kind="filter"),
             lambda: sink(scan().filter(WANTED)), v1_job=lambda: None),
    Scenario("sort", ["SortRow"], lambda: through("SortRow", {"criteria": SORT}),
             lambda: sink(scan().sort(["dept", "amount"], descending=[False, True], nulls_last=True, maintain_order=True))),
    Scenario("filter columns", ["FilterColumns"], lambda: through("FilterColumns", {}, KEEP_OUT),
             lambda: sink(scan().select([name for name, _ in KEEP_OUT]))),
    Scenario("unique", ["UniqueRow"],
             lambda: through("UniqueRow", {"key_columns": [{"column": "account", "case_sensitive": True}], "keep": "first"},
                             out_kind="unique"),
             lambda: sink(scan().unique(subset=["account"], keep="first", maintain_order=True))),
    Scenario("aggregate", ["AggregateRow"], lambda: through("AggregateRow", AGG_CONFIG, AGG_OUT), hand_aggregate,
             same_bytes=False),
    Scenario("join", ["Join"], join_job,
             lambda: sink(scan().join(scan("cities.csv", CITY), on="city", how="left", maintain_order="left"))),
    Scenario("map (lookup, expressions, filter)", ["PyMap"], lambda: map_job("PyMap"), hand_map, same_bytes=False),
    Scenario("rejects (1 row in 100 unreadable)", [], reject_job, hand_reject),
]


# ------------------------------------------------------------------
# Running
# ------------------------------------------------------------------

def timed(work: Callable[[], Any]) -> float:
    started = time.perf_counter()
    work()
    return time.perf_counter() - started


def run_v1(job_config: Dict[str, Any]) -> None:
    import copy
    import warnings

    from src.v1.engine.engine import ETLEngine

    made = copy.deepcopy(job_config)
    for component in made["components"]:
        if component["type"] == "FileOutputDelimited":
            component["config"]["filepath"] = component["config"]["filepath"].replace("_v2", "_v1")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = ETLEngine(made).execute()
    if result.get("status") != "success":
        raise RuntimeError(f"v1: {result.get('status')}: {result.get('error', '')}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mb", type=float, default=500, help="Size of the generated file in MB (default 500).")
    parser.add_argument("--only", default="", help="Comma-separated scenario names (or their first words).")
    parser.add_argument("--keep", action="store_true", help="Leave the scratch folder in place.")
    parser.add_argument("--v1", action="store_true", help="Also run each job on v1.")
    args = parser.parse_args(argv)

    folder = Path(tempfile.mkdtemp(prefix="v2_bench_", dir=os.environ.get("V2_TEMP_DIR") or None))
    previous = os.getcwd()
    os.chdir(folder)
    try:
        rows = generate(folder, args.mb)
        size = os.path.getsize("big.csv") / 1e6
        print(f"input: {rows} rows, {size:.0f} MB, {len(COLUMNS)} columns; polars {pl.__version__}, "
              f"{os.cpu_count()} cores; scratch folder {folder}")
        header = f"{'scenario':36s} {'rows out':>10s} {'v2 s':>7s} {'hand s':>7s} {'ratio':>6s}"
        print(header + (f" {'v1 s':>7s} {'v1/v2':>6s}" if args.v1 else "") + "  output")
        wanted = [name.strip().lower() for name in args.only.split(",") if name.strip()]
        for scenario in SCENARIOS:
            if wanted and not any(scenario.name.lower().startswith(name) for name in wanted):
                continue
            missing = [name for name in scenario.needs if REGISTRY.get(name) is None]
            if missing:
                print(f"{scenario.name:36s} skipped: no {', '.join(missing)} component")
                continue
            config = scenario.job_config()
            result = None

            def on_v2() -> None:
                nonlocal result
                result = run_job(config)

            v2_seconds = timed(on_v2)
            if result.status != "success":
                print(f"{scenario.name:36s} FAILED on v2: {result.error}")
                continue
            hand_seconds = timed(scenario.by_hand)
            verdict = "-"
            if scenario.same_bytes:
                verdict = "same bytes" if filecmp.cmp("out_v2.csv", "out_hand.csv", shallow=False) else "DIFFERENT"
            line = (f"{scenario.name:36s} {result.rows.get('out', 0):>10d} {v2_seconds:7.2f} {hand_seconds:7.2f} "
                    f"{v2_seconds / hand_seconds:6.1f}")
            if args.v1:
                v1_config = scenario.v1_job() if scenario.v1_job is not None else config
                if v1_config is None:
                    line += f" {'-':>7s} {'-':>6s}"
                else:
                    v1_seconds = timed(lambda: run_v1(v1_config))
                    same = filecmp.cmp("out_v2.csv", "out_v1.csv", shallow=False)
                    line += f" {v1_seconds:7.2f} {v1_seconds / v2_seconds:6.1f}"
                    verdict += "; v1 " + ("same bytes" if same else "DIFFERENT")
            print(line + "  " + verdict, flush=True)
    finally:
        os.chdir(previous)
        if not args.keep:
            shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
