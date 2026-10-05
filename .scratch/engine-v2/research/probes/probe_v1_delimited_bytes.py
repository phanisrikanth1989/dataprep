"""Probe: what v1 holds in memory and writes for delimited files.

Runs the v1 engine (src/v1, pandas) on small FileInputDelimited ->
FileOutputDelimited jobs and prints, per case: the input bytes, the schema and
the config keys that differ from the baseline, what the reader hands
downstream (dtypes and cell values), what the reject flow carries, and the
exact bytes written. Evidence for ../2026-10-05-v1-delimited-bytes.md; the
case ids in brackets are the ones its tables cite.

Run from the repo root:
    .venv/bin/python .scratch/engine-v2/research/probes/probe_v1_delimited_bytes.py

Read-only on the repo: no bytecode is written, and every file it creates
(inputs, job configs, outputs) lives in one fresh directory under the system
temp directory. No Java: java_config.enabled is false and no config string
carries a {{java}} marker. It documents v1 as found; it is not a test.

Schema shorthand used below: "name:type" joined by ", ", with "!" for
nullable false, "#n" for precision n and "@pattern" for date_pattern, e.g.
"id:int!, amt:Decimal#2, d:datetime@%Y-%m-%d".

Output is ASCII only: file contents print as Python bytes literals, and a
non-ASCII character inside held text prints as the backslash escape of its
code point (so U+00E9 shows as backslash-x-e9). Temp paths print as <tmp>.
"""
import copy
import json
import logging
import os
import platform
import random
import sys
import tempfile
import warnings
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow  # noqa: E402

from src.v1.engine.components.file.file_input_delimited import FileInputDelimited  # noqa: E402
from src.v1.engine.engine import ETLEngine  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="probe_v1_delimited_"))
READER, WRITER, REJSINK = "tFileInputDelimited_1", "tFileOutputDelimited_1", "tFileOutputDelimited_2"

# Baselines: the key sets the Talend converter emits (see
# tests/talend_xml_samples/converted_jsons/Job_tFileInputDelimited_0.1.json and
# Job_tFileOutputDelimited_0.1.json), with encoding UTF-8 on both sides.
READER_BASE = {
    "csv_option": False, "row_separator": "\\n", "csv_row_separator": "\\n",
    "fieldseparator": ";", "escape_char": "\"", "text_enclosure": "\"",
    "header_rows": 0, "footer_rows": 0, "limit": "", "remove_empty_row": True,
    "uncompress": False, "die_on_error": False, "advanced_separator": False,
    "thousands_separator": ",", "decimal_separator": ".", "random": False,
    "nb_random": 10, "trim_all": False, "check_fields_num": False,
    "check_date": False, "encoding": "UTF-8", "split_record": False,
    "enable_decode": False, "trim_select": [], "decode_cols": [],
    "tstatcatcher_stats": False, "label": "",
}
WRITER_BASE = {
    "usestream": False, "streamname": "outputStream", "row_separator": "\\n",
    "fieldseparator": ";", "append": False, "include_header": False,
    "compress": False, "advanced_separator": False, "thousands_separator": ",",
    "decimal_separator": ".", "csv_option": False, "escape_char": "\"",
    "text_enclosure": "\"", "os_line_separator": True, "csvrowseparator": "\\n",
    "create_directory": True, "split": False, "split_every": "1000",
    "flushonrow": False, "flush_row_count": "1", "row_mode": False,
    "encoding": "UTF-8", "delete_empty_file": False, "file_exist_exception": True,
    "tstatcatcher_stats": False, "label": "",
}
KNOWN_WARNING = "'str' dtypes are included by select_dtypes"
CSV = {"csv_option": True}
CFN = {"check_fields_num": True}
_count = [0]


class _Collect(logging.Handler):
    """Collect WARNING+ records from the v1 loggers instead of printing them."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(f"{record.levelname} {record.name.split('.')[-1]}: {record.getMessage()}")


LOGS = _Collect()
logging.getLogger().addHandler(LOGS)
logging.getLogger().setLevel(logging.WARNING)


def out(text=""):
    """Print ASCII only."""
    print(str(text).encode("ascii", "backslashreplace").decode())


def schema(spec):
    """Expand the shorthand (see module docstring) into a v1 schema list."""
    if not isinstance(spec, str):
        return spec
    cols = []
    for part in [p for p in spec.split(", ") if p]:
        name, typ = part.split(":", 1)
        col = {"name": name, "nullable": True, "key": False}
        if "@" in typ:
            typ, col["date_pattern"] = typ.split("@", 1)
        if "#" in typ:
            typ, prec = typ.split("#", 1)
            col["precision"] = int(prec)
        if typ.endswith("!"):
            typ, col["nullable"] = typ[:-1], False
        col["type"] = typ
        cols.append(col)
    return cols


def run(data, spec, reader=None, writer=None, wschema=None, wschema_out=None, reject_sink=False,
        drop_reader=(), drop_writer=(), workdir=None, pre=None):
    """Run one FileInputDelimited -> FileOutputDelimited job; return what was observed.

    wschema is the writer's schema.input (default: a copy of the reader's
    schema.output, as in a converted job); wschema_out is the writer's
    schema.output (default [], as the converter emits). reject_sink wires the
    reader's reject flow to a second FileOutputDelimited (header on, empty schema).
    pre maps file names to bytes written into the job directory before the run.
    """
    _count[0] += 1
    d = Path(workdir) if workdir else TMP / f"case{_count[0]:04d}"
    d.mkdir(parents=True, exist_ok=True)
    for name, content in (pre or {}).items():
        (d / name).write_bytes(content)
    existing = {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*"))
                if p.is_file() and p.name not in ("in.csv", "job.json")}
    if data is not None:
        (d / "in.csv").write_bytes(data)
    rcfg = {**READER_BASE, **(reader or {}), "filepath": str(d / "in.csv")}
    wcfg = {**WRITER_BASE, "filepath": str(d / "out.csv"), **(writer or {})}
    for key in drop_reader:
        rcfg.pop(key, None)
    for key in drop_writer:
        wcfg.pop(key, None)
    rschema = schema(spec)
    comps = [
        {"id": READER, "type": "FileInputDelimited", "original_type": "tFileInputDelimited", "config": rcfg,
         "schema": {"input": [], "output": rschema}, "inputs": [],
         "outputs": ["row1"] + (["rej1"] if reject_sink else [])},
        {"id": WRITER, "type": "FileOutputDelimited", "original_type": "tFileOutputDelimited", "config": wcfg,
         "schema": {"input": copy.deepcopy(rschema) if wschema is None else schema(wschema),
                    "output": schema(wschema_out or [])},
         "inputs": ["row1"], "outputs": []},
    ]
    flows = [{"name": "row1", "from": READER, "to": WRITER, "type": "flow"}]
    if reject_sink:
        comps.append({"id": REJSINK, "type": "FileOutputDelimited", "original_type": "tFileOutputDelimited",
                      "config": {**WRITER_BASE, "include_header": True, "filepath": str(d / "rej.csv")},
                      "schema": {"input": [], "output": []}, "inputs": ["rej1"], "outputs": []})
        flows.append({"name": "rej1", "from": READER, "to": REJSINK, "type": "reject"})
    job = {"job_name": "probe", "job_type": "Standard", "default_context": "Default",
           "context": {"Default": {}}, "components": comps, "flows": flows, "triggers": [],
           "subjobs": {"subjob_1": [c["id"] for c in comps]},
           "java_config": {"enabled": False, "routines": [], "libraries": []}}
    (d / "job.json").write_text(json.dumps(job, indent=1), encoding="utf-8")

    LOGS.records.clear()
    held, obs = {}, {"dir": d, "errors": [], "counts": "", "existing": existing}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            engine = ETLEngine(str(d / "job.json"))
            comp = engine.components[READER]
            original = comp.execute

            def spy(input_data=None):
                result = original(input_data)
                held["main"], held["reject"] = result.get("main"), result.get("reject")
                return result

            comp.execute = spy  # instance attribute only; nothing under src/ is changed
            stats = engine.execute()
            obs["status"] = stats.get("status")
            cstats = stats.get("component_stats") or {}
            for cid, cs in cstats.items():
                if cs.get("error"):
                    obs["errors"].append(f"{cid}: {cs['error']}")
                elif cs.get("status") == "skipped":
                    obs["errors"].append(f"{cid}: skipped")
            if stats.get("error"):
                obs["errors"].append(f"job: {stats['error']}")
            rs = cstats.get(READER, {})
            if "NB_LINE" in rs:
                obs["counts"] = f"reader NB_LINE={rs['NB_LINE']} OK={rs['NB_LINE_OK']} REJECT={rs['NB_LINE_REJECT']}"
        except Exception as exc:  # noqa: BLE001
            obs["status"] = "RAISED"
            obs["errors"].append(f"{type(exc).__name__}: {exc}")
    obs["errors"] = [e.replace(str(d), "<tmp>") for e in obs["errors"]]
    noise = ("executor:", "engine:")
    obs["log"] = sorted(r.replace(str(d), "<tmp>") for r in LOGS.records
                        if not any(n in r.split(" ", 2)[1] for n in noise) and "] failed: " not in r)
    obs["pywarn"] = sorted({f"{w.category.__name__}: {w.message}" for w in caught if KNOWN_WARNING not in str(w.message)})
    obs["main"], obs["reject"] = held.get("main"), held.get("reject")
    outp = Path(wcfg["filepath"])
    obs["out"] = outp.read_bytes() if outp.is_file() else None
    obs["rej"] = (d / "rej.csv").read_bytes() if (d / "rej.csv").is_file() else None
    skip = {d / "in.csv", d / "job.json", d / "rej.csv", outp}
    obs["others"] = {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file() and p not in skip}
    return obs


def fmt_cfg(cfg, dropped=()):
    parts = []
    for key, value in (cfg or {}).items():
        if key == "filepath":  # every job directory is TMP/<name>; show the path below it
            value = "<tmp>/" + "/".join(Path(value).relative_to(TMP).parts[1:])
        parts.append(f"{key}={value!r}")
    parts += [f"{key}=<key absent>" for key in dropped]
    return " ".join(parts) if parts else "-"


def fmt_frame(df):
    lines = [", ".join(f"{c}={t}" for c, t in df.dtypes.items()) or "(no columns)"]
    lines += ["(" + ", ".join(repr(v) for v in row) + ")" for row in df.itertuples(index=False, name=None)]
    return lines


def fmt_out(data):
    return "<no file>" if data is None else repr(data)


def case(cid, title, data, spec, show_held=True, **kw):
    """Run one job and print the full observation block."""
    o = run(data, spec, **kw)
    out(f"\n[{cid}] {title}")
    out(f"  input    {fmt_out(data) if data is not None else '<input file absent>'}")
    out(f"  schema   {spec if isinstance(spec, str) else json.dumps(spec)}")
    if kw.get("reader") or kw.get("drop_reader"):
        out(f"  reader   {fmt_cfg(kw.get('reader'), kw.get('drop_reader', ()))}")
    if kw.get("writer") or kw.get("drop_writer"):
        out(f"  writer   {fmt_cfg(kw.get('writer'), kw.get('drop_writer', ()))}")
    if kw.get("wschema") is not None:
        out(f"  wschema  schema.input = {kw['wschema'] if isinstance(kw['wschema'], str) and kw['wschema'] else '[]'}")
    if kw.get("wschema_out"):
        out(f"  wschema  schema.output = {kw['wschema_out']}")
    for name, content in o["existing"].items():
        out(f"  existing {name}: {content!r}")
    out(f"  status   {o['status']}" + (f" | {o['counts']}" if o["counts"] else "")
        + (" | reject sink wired" if kw.get("reject_sink") else ""))
    for err in o["errors"]:
        out(f"  error    {err!r}")
    for rec in o["log"] + o["pywarn"]:
        out(f"  log      {rec}")
    if show_held and o["main"] is not None:
        for i, line in enumerate(fmt_frame(o["main"])):
            out(f"  {'held    ' if i == 0 else '        '} {line}")
    if o["reject"] is not None:
        for i, line in enumerate(fmt_frame(o["reject"])):
            out(f"  {'reject  ' if i == 0 else '        '} {line}")
    out(f"  output   {fmt_out(o['out'])}")
    if kw.get("reject_sink"):
        out(f"  rejfile  {fmt_out(o['rej'])}")
    for name, content in o["others"].items():
        out(f"  file     {name}: {content!r}")
    return o


def column(cid, title, tspec, values, **kw):
    """One value per row in column v of a 'k:str, v:<tspec>' file (keys r1, r2, ...)."""
    data = b"".join(b"r%d;" % i + v + b"\n" for i, v in enumerate(values, 1))
    return case(cid, title, data, f"k:str, v:{tspec}", **kw)


def brief(cid, o, key, col="v", note=""):
    """One line: what the row with first column == key holds in col, and the bytes written."""
    main, rej = o["main"], o["reject"]
    cell, dtype = "<no frame>", "-"
    if main is not None and col in main.columns:
        dtype = str(main.dtypes[col])
        hits = [row for row in main.itertuples(index=False, name=None) if str(row[0]) == key]
        cell = repr(hits[0][list(main.columns).index(col)]) if hits else "<row absent>"
    extra = ""
    if rej is not None and len(rej):
        extra += " | reject " + "; ".join(repr(tuple(r)) for r in rej.itertuples(index=False, name=None))
    if o["status"] != "success":
        extra += f" | status {o['status']} " + "; ".join(o["errors"])
    for rec in o["log"]:
        extra += f" | log {rec}"
    out(f"[{cid}] {note}dtype={dtype} held={cell} written={fmt_out(o['out'])}{extra}")


def head(title):
    out("\n" + "=" * 100)
    out(title)
    out("=" * 100)


def newdir(name):
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------------- 0
def environment():
    head("0. Environment")
    out(f"python {sys.version.split()[0]} | pandas {pd.__version__} | numpy {np.__version__} | pyarrow {pyarrow.__version__}")
    out(f"platform {platform.platform()} | os.linesep {os.linesep!r}")
    probe = pd.Series(["x"], dtype="str")
    storage, na_value = getattr(probe.dtype, "storage", "n/a"), getattr(probe.dtype, "na_value", "n/a")
    out(f"dtype of a dtype=str column: {probe.dtype!r} storage={storage} na_value={na_value!r}")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        selected = list(pd.DataFrame({"a": probe}).select_dtypes(include=["object"]).columns)
    out(f"select_dtypes(include=['object']) on that column returns {selected} (the reader's scrub and trim_all rely on")
    out("this, file_input_delimited.py:262 and :647); warnings it raised, which every reader run repeats:")
    for w in caught:
        out(f"  {w.category.__name__}: {str(w.message).splitlines()[0]}")
    if not caught:
        out("  (none)")
    out(f"baseline reader config: {json.dumps(READER_BASE)}")
    out(f"baseline writer config: {json.dumps(WRITER_BASE)}")
    out("each case lists only the keys that differ; the writer's schema.input copies the reader's schema.output unless shown")


# --------------------------------------------------------------------------- 1
def area1():
    head("1. Types on read and write")
    six = "s:str, i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2"
    data = b"a;1;1.5;true;2024-01-31;12.345\nb;2;2.0;false;2023-12-01;7\n"
    case("1.01", "six types, nullable true", data, six)
    case("1.02", "six types, nullable false", data,
         "s:str!, i:int!, f:float!, b:bool!, d:datetime!@%Y-%m-%d, m:Decimal!#2")
    case("1.03", "six types, writer schema.input empty: nothing formats the values", data, six, wschema=[])
    case("1.04", "writer schema.input names differ from the frame's (upper case)", data, six,
         writer={"include_header": True},
         wschema="S:str, I:int, F:float, B:bool, D:datetime@%Y-%m-%d, M:Decimal#2")
    column("1.05", "bool spellings the vectorized map accepts", "bool",
           [b"true", b"false", b"1", b"0", b"yes", b"no", b"True", b"False", b"Yes", b"No", b"YES", b"NO"])
    column("1.06", "bool spellings outside the map (whole column falls back to per-row)", "bool",
           [b"true", b"TRUE", b"FALSE", b" true ", b"", b"Y", b"N", b"t", b"f", b"on", b"2"])
    column("1.07", "datetime pattern %d/%m/%Y", "datetime@%d/%m/%Y", [b"31/01/2024", b"01/02/2024"])
    column("1.08", "datetime pattern with time", "datetime@%Y-%m-%d %H:%M:%S", [b"2024-01-31 10:11:12", b"2024-01-31 00:00:00"])
    column("1.09", "datetime pattern with %f (what Java SSS converts to)", "datetime@%Y-%m-%d %H:%M:%S.%f",
           [b"2024-01-31 10:11:12.123", b"2024-01-31 10:11:12.123456", b"2024-01-31 10:11:12.5"])
    column("1.10", "datetime pattern with month name", "datetime@%d-%b-%Y", [b"31-Jan-2024", b"01-FEB-2024"])
    column("1.11", "datetime: lenient and strict inputs under %Y-%m-%d", "datetime@%Y-%m-%d",
           [b"2024-01-31", b"2024-1-5", b" 2024-02-01 ", b"2024-02-30", b"2024-01-31 10:00:00", b"31/01/2024"])
    column("1.12", "datetime: Java-dialect pattern on the reader, die_on_error false", "datetime@yyyy-MM-dd",
           [b"2024-01-31", b"1999-12-31"])
    column("1.13", "datetime: Java-dialect pattern on the reader, die_on_error true", "datetime@yyyy-MM-dd",
           [b"2024-01-31"], reader={"die_on_error": True})
    column("1.14", "datetime: Java-dialect pattern on the writer only", "datetime@%Y-%m-%d", [b"2024-01-31", b""],
           wschema="k:str, v:datetime@yyyy-MM-dd")
    column("1.15", "datetime: no date_pattern on either side (ISO text)", "datetime",
           [b"2024-01-31", b"1999-12-31 01:02:03.5"])
    column("1.16", "datetime: no date_pattern, slash dates", "datetime", [b"01/02/2024", b"31/01/2024"])
    column("1.17", "datetime: extreme years", "datetime@%Y-%m-%d",
           [b"0001-01-01", b"0999-12-31", b"1677-09-20", b"2262-04-12", b"9999-12-31"])
    column("1.18", "datetime: reader %Y-%m-%d, writer pattern %d/%m/%Y %H:%M:%S", "datetime@%Y-%m-%d",
           [b"2024-01-31", b""], wschema="k:str, v:datetime@%d/%m/%Y %H:%M:%S")
    column("1.19", "datetime: reader has a pattern, writer declares datetime without one", "datetime@%Y-%m-%d %H:%M:%S.%f",
           [b"2024-01-31 10:11:12.123", b"2024-01-31 00:00:00.0", b""], wschema="k:str, v:datetime")
    column("1.20", "str in the frame, writer declares datetime@%Y-%m-%d", "str",
           [b"2024-01-31", b"31/01/2024", b"junk", b""], wschema="k:str, v:datetime@%Y-%m-%d")
    column("1.21", "Decimal: reader precision 2, writer declares precision 4", "Decimal#2", [b"1.005", b"7", b""],
           wschema="k:str, v:Decimal#4")
    column("1.22", "Decimal: reader precision 2, writer declares no precision", "Decimal#2", [b"1.005", b"7", b"30200"],
           wschema="k:str, v:Decimal")
    column("1.23", "Decimal held, writer declares float", "Decimal#2", [b"1.005", b"7"], wschema="k:str, v:float")
    column("1.24", "float held, writer declares Decimal#2", "float", [b"2.005", b"2.675", b"3", b""], wschema="k:str, v:Decimal#2")
    column("1.25", "str held, writer declares Decimal#2 / Decimal / bool (three writers, same frame)", "str",
           [b"7.10", b"abc", b"", b"1e3", b"TRUE", b"None"], wschema="k:str, v:Decimal#2")
    column("1.26", "  ... writer declares Decimal without precision", "str",
           [b"7.10", b"abc", b"", b"1e3", b"TRUE", b"None"], wschema="k:str, v:Decimal")
    column("1.27", "  ... writer declares bool", "str",
           [b"7.10", b"abc", b"", b"1e3", b"TRUE", b"None"], wschema="k:str, v:bool")
    case("1.28", "length is not enforced (str length 3, int length 1)", b"12345;abcdefghij\n",
         [{"name": "a", "type": "int", "nullable": True, "length": 1}, {"name": "b", "type": "str", "nullable": True, "length": 3}])


# --------------------------------------------------------------------------- 2
GOOD = {"str": ("str", "ok"), "int": ("int", "5"), "float": ("float", "5.5"), "bool": ("bool", "true"),
        "datetime": ("datetime@%Y-%m-%d", "2024-01-31"), "Decimal": ("Decimal#2", "5.5")}
MISSING = [("empty", b""), ("quoted", b'""'), ("spaces", b"   "), ("NaN", b"NaN"), ("null", b"null"),
           ("NA", b"NA"), ("None", b"None")]


def area2():
    head("2. Missing values")
    out("Matrix: the file is b'1;<good>\\n2;<text>\\n', schema 'id:int, v:<type>' (Decimal has precision 2);")
    out("each line shows what row 2 holds in column v and the whole output file. plain = csv_option false.")
    for mode, reader in (("plain", None), ("csv", CSV)):
        for tname, (tspec, good) in GOOD.items():
            out("")
            for vname, raw in MISSING:
                o = run(b"1;" + good.encode() + b"\n2;" + raw + b"\n", f"id:int, v:{tspec}", reader=reader)
                brief(f"2.{mode}.{tname}.{vname}", o, "2", note=f"text={raw!r} ")
    out("\nnullable false: the file is b'1;<good>;a\\n2;<text>;b\\n3;<good>;c\\n', schema 'id:int, v:<type>!, t:str'")
    for die in (False, True, "absent"):
        kw = {"drop_reader": ("die_on_error",)} if die == "absent" else {"reader": {"die_on_error": die}}
        for tname, (tspec, good) in GOOD.items():
            tspec = tspec.replace("#", "!#").replace("@", "!@") if ("#" in tspec or "@" in tspec) else tspec + "!"
            for vname, raw in (("empty", b""), ("spaces", b"  ")):
                g = good.encode()
                o = run(b"1;" + g + b";a\n2;" + raw + b";b\n3;" + g + b";c\n", f"id:int, v:{tspec}, t:str", **kw)
                brief(f"2.notnull.{tname}.{vname}.die={die}", o, "2", note=f"text={raw!r} ")
        out("")
    case("2.90", "what the reject file carries for a nullable-false violation (die_on_error false)",
         b"1;5;2024-01-31;a\n2;;;b\n3;7;2024-02-01;c\n", "id:int, n:int!, d:datetime@%Y-%m-%d, t:str", reject_sink=True)
    case("2.91", "empty value in every typed column, fast path", b"1;1.5;true;2024-01-31;2.5;x\n;;;;;y\n",
         "i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2, s:str")
    case("2.92", "same file, chunked path (check_fields_num true)", b"1;1.5;true;2024-01-31;2.5;x\n;;;;;y\n",
         "i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2, s:str", reader=CFN)
    case("2.93", "Decimal without precision, empty value, chunked path", b"1;1.5;x\n2;;y\n", "id:int, m:Decimal, s:str", reader=CFN)
    case("2.94", "nullable-false Decimal, empty value, chunked path", b"1;1.5;x\n2;;y\n", "id:int, m:Decimal!#2, s:str", reader=CFN)
    case("2.95", "csv_option true writer: how nulls and empty text are written",
         b"1;1.5;true;2024-01-31;2.5;x\n;;;;;y\n2;;;;;\n", "i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2, s:str", writer=CSV)


# --------------------------------------------------------------------------- 3
NUMS = [b"1", b"1.0", b"1.50", b"30200.00", b"1e5", b"1234567890123456789", b"9223372036854775807",
        b"9223372036854775808", b"12345678901234567890123", b"-0", b"-0.0", b"007", b"+5", b" 7 ", b"1_000",
        b"1,000", b"0x1A", b"inf"]


def one(cid, tspec, raw, **kw):
    brief(cid, run(b"x;" + raw + b"\n", f"k:str, v:{tspec}", **kw), "x", note=f"{tspec} text={raw!r} ")


def area3():
    head("3. Numbers")
    out("One value per file: the file is b'x;<text>\\n', schema 'k:str, v:<type>'.")
    for tspec in ("str", "int", "int!", "float", "Decimal#2", "Decimal"):
        out("")
        for i, raw in enumerate(NUMS, 1):
            one(f"3.one.{tspec}.{i:02d}", tspec, raw)
    out("\nfloat text -> repr written")
    for i, raw in enumerate([b"0.1", b"0.30000000000000004", b"1.23456789012345678", b"123456789.123456789", b"1e15",
                             b"1e16", b"1e22", b"0.0001", b"0.00001", b"1.7976931348623157e308", b"5e-324", b"2.50",
                             b"-inf", b"nan"], 1):
        one(f"3.float.{i:02d}", "float", raw)
    out("\nfloat with schema precision (rounding happens on read)")
    for prec in (0, 2):
        for i, raw in enumerate([b"0.5", b"1.5", b"2.5", b"1.005", b"2.675", b"1.234567", b"30200.00", b"-0.004"], 1):
            one(f"3.floatprec{prec}.{i:02d}", f"float#{prec}", raw)
    out("\nint with schema precision 0 (the converted sample carries it)")
    for i, raw in enumerate([b"1", b"1.50"], 1):
        one(f"3.intprec0.{i:02d}", "int#0", raw)
    out("\nDecimal precision 0, 2, 4 and absent")
    for tspec in ("Decimal#0", "Decimal#2", "Decimal#4", "Decimal"):
        for i, raw in enumerate([b"1.50", b"0.5", b"2.5", b"1.005", b"2.675", b"-1.005", b"1e5", b"1E-7", b"0.00",
                                 b"100", b"-0", b"123456789012345678901234567890.125",
                                 b"0.1234567890123456789012345678901"], 1):
            one(f"3.dec.{tspec}.{i:02d}", tspec, raw)
        out("")
    out("Which texts make the reader's vectorized conversion raise (FileInputDelimited._vectorized_convert on")
    out("['5', <text>] as dtype str); a raise sends the WHOLE column down the per-row Python path:")
    for typ in ("int", "float"):
        verdicts = []
        for text in ["", '""', "   ", " 7 ", "NaN", "nan", "null", "NA", "None", "inf", "1e5", "1.50", "1_000", "1,000", "0x1A", "TRUE"]:
            try:
                res = FileInputDelimited._vectorized_convert(pd.Series(["5", text], dtype="str"), typ, {})
                verdicts.append(f"{text!r}->ok({res.dtype})")
            except Exception:  # noqa: BLE001
                verdicts.append(f"{text!r}->RAISES")
        out(f"[3.vec.{typ}] " + " ".join(verdicts))
    column("3.c01", "int: all whole numbers", "int", [b"1", b"2"])
    column("3.c02", "int: one fractional value turns the column to float", "int", [b"1", b"1.50"])
    column("3.c03", "int: 19 digits beside a plain int", "int", [b"1234567890123456789", b"5"])
    column("3.c04", "int: 19 digits beside an empty value", "int", [b"1234567890123456789", b""])
    column("3.c05", "int: 19 digits beside a float-looking value", "int", [b"1234567890123456789", b"1.0"])
    column("3.c06", "int: 19 digits beside a whitespace-only value (per-row fallback)", "int", [b"1234567890123456789", b"   "])
    column("3.c07", "int: fractions beside a whitespace-only value (per-row fallback truncates)", "int", [b"1.50", b"2.9", b"-2.9", b"   "])
    column("3.c08", "int: 1e5 / NaN / 7", "int", [b"1e5", b"NaN", b"7"])
    column("3.c09", "int nullable false: fractions and overflow", "int!", [b"1.50", b"2.9", b"-2.9"])
    column("3.c10", "float: long decimals, vectorized", "float", [b"0.30000000000000004", b"-0", b"9345049367.241609"])
    column("3.c11", "float: same values beside a whitespace-only value (per-row fallback)", "float",
           [b"0.30000000000000004", b"-0", b"9345049367.241609", b"   "])
    column("3.c12", "float: same values beside the text NaN (per-row fallback)", "float",
           [b"0.30000000000000004", b"-0", b"9345049367.241609", b"NaN"])
    column("3.c13", "leading zeros in a str and an int column, thousands text in str", "str", [b"007", b"0", b"1,000", b"-0", b"1e5"])
    column("3.c14", "leading zeros in an int column", "int", [b"007", b"0", b"-0", b"00"])
    column("3.k01", "chunked path (check_fields_num true): int", "int",
           [b"1", b"1.50", b"2.9", b"1e5", b"1_000", b" 7 ", b"1234567890123456789", b"-0"], reader=CFN)
    column("3.k02", "chunked path: float", "float", [b"0.30000000000000004", b"1", b"-0", b"NaN", b"inf", b"9345049367.241609"], reader=CFN)
    column("3.k03", "chunked path: Decimal precision 2", "Decimal#2", [b"1.005", b"7", b"1e5", b"NaN"], reader=CFN)
    case("3.k04", "advanced_separator true with decimal ',' and thousands '.' (both sides)", b"1;1.234,56\n2;7,5\n3;8\n",
         "id:int, f:float", reader={"advanced_separator": True, "thousands_separator": ".", "decimal_separator": ","},
         writer={"advanced_separator": True, "thousands_separator": ".", "decimal_separator": ","})
    out("\n[3.parse] pandas.to_numeric versus Python float() on random decimal text (20000 strings per row, seed 7):")
    rng = random.Random(7)
    for int_digits, frac_digits in [(5, 2), (9, 2), (13, 2), (15, 2), (1, 14), (1, 15), (1, 16), (10, 6), (0, 15), (0, 17)]:
        vals = []
        for _ in range(20000):
            whole = str(rng.randint(10 ** (int_digits - 1), 10 ** int_digits - 1)) if int_digits else "0"
            vals.append(whole + "." + "".join(rng.choice("0123456789") for _ in range(frac_digits)))
        got = pd.to_numeric(pd.Series(vals, dtype="str"), errors="raise").astype(float).to_numpy()
        want = np.array([float(v) for v in vals])
        diff = got != want
        eg = ""
        if diff.any():
            k = int(np.argmax(diff))
            eg = f" e.g. {vals[k]!r}: to_numeric {float(got[k])!r}, float() {float(want[k])!r}"
        out(f"  {int_digits + frac_digits:2} significant digits ({int_digits}.{frac_digits}): {int(diff.sum()):5} of 20000 differ{eg}")


# --------------------------------------------------------------------------- 4
def area4():
    head("4. Bad values")
    data = b"1;alice;2024-01-31;10.5\nx2;bob;2024-02-01;20\n3;carol;2024-02-30;30\n4;dave;2024-03-01;\n"
    spec = "id:int, name:str, d:datetime@%Y-%m-%d, amt:float"
    case("4.01", "text in int + bad date, die_on_error false", data, spec, reject_sink=True)
    case("4.02", "same, die_on_error true", data, spec, reader={"die_on_error": True}, reject_sink=True)
    case("4.03", "same, die_on_error key absent", data, spec, drop_reader=("die_on_error",), reject_sink=True)
    case("4.04", "same, die_on_error false, no reject sink wired", data, spec)
    case("4.05", "same, check_fields_num true (chunked path)", data, spec, reader=CFN, reject_sink=True)
    case("4.06", "same, check_date true (chunked path)", data, spec, reader={"check_date": True}, reject_sink=True)
    case("4.07", "same, check_date true and die_on_error true", data, spec, reader={"check_date": True, "die_on_error": True}, reject_sink=True)
    case("4.08", "clean data with a reject sink wired", b"1;alice;2024-01-31;10.5\n", spec, reject_sink=True)
    case("4.09", "two bad columns in one row: only the first is reported", b"x;a;notadate;zz\n2;b;2024-01-01;1\n", spec, reject_sink=True)
    case("4.10", "bad text in a Decimal column, fast path, die_on_error true", b"1;1.5\n2;abc\n3;1,000\n", "id:int, m:Decimal!#2",
         reader={"die_on_error": True})
    case("4.11", "bad text in a Decimal column, chunked path, die_on_error false", b"1;1.5\n2;abc\n", "id:int, m:Decimal#2", reader=CFN)
    case("4.12", "die_on_error given as the string 'false'", b"1;a\nq;b\n", "id:int, name:str", reader={"die_on_error": "false"})
    case("4.13", "a line with too many fields, die_on_error false", b"1;a\n2;b;c\n", "id:int, name:str")
    case("4.14", "a line with too many fields, die_on_error true", b"1;a\n2;b;c\n", "id:int, name:str", reader={"die_on_error": True})
    case("4.15", "input file missing", None, "id:int, name:str")
    case("4.16", "what 'Line: n' counts (header_rows 2, a blank line, bad value on file line 5)", b"h;h\nh;h\n1;a\n\nx;b\n",
         "id:int, name:str", reader={"header_rows": 2, "check_fields_num": True})


# --------------------------------------------------------------------------- 5
def area5():
    head("5. Text")
    s3, s2 = "a:str, b:str, c:str", "a:str, b:str"
    q = b'1;"x;y";z\n2;"say ""hi""";q\n3;"";""\n'
    case("5.01", "plain: quote characters are data", b'1;"x";z\n2;say "hi";q\n3;"";""\n', s3)
    case("5.02", "plain: separator inside quotes, first line (4 raw fields, schema 3)", b'1;"x;y";z\n2;p;q\n', s3)
    case("5.03", "plain: separator inside quotes, later line", b'1;p;q\n2;"x;y";z\n', s3)
    case("5.04", "csv read, plain write", q, s3, reader=CSV)
    case("5.05", "csv read, csv write", q, s3, reader=CSV, writer=CSV)
    case("5.06", "plain write of values holding the separator, a quote and a newline", b'1,"x;y","say ""hi"""\n2,"l1\nl2",q\n',
         s3, reader={"csv_option": True, "fieldseparator": ","})
    case("5.07", "csv: LF inside a quoted field", b'1;"l1\nl2";z\n2;p;q\n', s3, reader=CSV, writer=CSV)
    case("5.08", "csv: CRLF inside a quoted field, CRLF rows", b'1;"l1\r\nl2";z\r\n2;p;q\r\n', s3, reader=CSV, writer=CSV)
    case("5.09", "csv: bare CR inside an unquoted field", b"1;x\ry;z\n2;p;q\n", s3, reader=CSV)
    case("5.10", "plain: LF inside quotes splits the row", b'1;"l1\nl2";z\n2;p;q\n', s3)
    case("5.11", "csv: quote in the middle of an unquoted field", b'1;ab"cd;z\n2;5" disk;q\n', s3, reader=CSV, writer=CSV)
    case("5.12", "csv: unterminated quote", b'1;"abc;z\n2;p;q\n', s3, reader=CSV, writer=CSV)
    case("5.13", "csv: space before the opening quote", b'1; "x;y";z\n', s3, reader=CSV, writer=CSV)
    apos = {"csv_option": True, "text_enclosure": "'", "escape_char": "'"}
    case("5.14", "csv: text_enclosure ' (escape_char ' too)", b"1;'x;y';'it''s'\n2;\"dq\";z\n", s3, reader=apos, writer=apos)
    back = {"csv_option": True, "escape_char": "\\"}
    case("5.15", "csv: escape_char backslash on both sides", b'1;"say \\"hi\\"";"a\\\\b"\n2;"x;y";plain\\n\n', s3, reader=back, writer=back)
    case("5.16", "csv: escape_char of two backslashes on the reader", b'1;"x";z\n', s3, reader={"csv_option": True, "escape_char": "\\\\"})
    case("5.17", "csv: escape_char of two backslashes on the writer", b"1;x;z\n", s3, writer={"csv_option": True, "escape_char": "\\\\"})
    case("5.18", "csv: empty text_enclosure on the reader", b'1;"x";z\n', s3, reader={"csv_option": True, "text_enclosure": ""})
    case("5.19", "csv: empty text_enclosure on the writer", b"1;x;z\n", s3, writer={"csv_option": True, "text_enclosure": ""})
    case("5.20", "plain: text_enclosure and escape_char are ignored", b"1;'x';z\n", s3, reader={"text_enclosure": "'"}, writer={"text_enclosure": "'"})
    bar = {"fieldseparator": "||"}
    case("5.21", "fieldseparator '||' plain", b"1||x|y||z\n2||p||q\n", s3, reader=bar, writer=bar)
    case("5.22", "fieldseparator '||' with csv_option true on both sides", b"1||x\n2||p\n", s3, reader={**bar, **CSV}, writer={**bar, **CSV})
    case("5.23", "fieldseparator backslash-t text", b"1\tx\tz\n", s3, reader={"fieldseparator": "\\t"}, writer={"fieldseparator": "\\t"})
    case("5.24", "fieldseparator '.*' (regex characters)", b"1.*x.*z\n", s3, reader={"fieldseparator": ".*"}, writer={"fieldseparator": ".*"})
    case("5.25", "fieldseparator ', ' with one row using a bare comma", b"1, x, z\n2, p,q\n", s3, reader={"fieldseparator": ", "}, writer={"fieldseparator": ", "})
    case("5.26", "fieldseparator empty on the reader", b"1;x;z\n", s3, reader={"fieldseparator": ""})
    case("5.27", "fieldseparator empty on the writer", b"1;x;z\n", s3, writer={"fieldseparator": ""})
    case("5.28", "plain: row_separator backslash-n text, file has CRLF", b"1;x;z\r\n2;p;q\r\n", s3)
    case("5.29", "plain: row_separator backslash-n text, file has bare CR rows", b"1;x;z\r2;p;q\r", s3)
    case("5.30", "plain: row_separator CRLF text, file has LF only", b"1;x;z\n2;p;q\n", s3, reader={"row_separator": "\\r\\n"})
    case("5.31", "plain: row_separator '@@'", b"1;x;z@@2;p;q@@", s3, reader={"row_separator": "@@"})
    case("5.32", "plain: row_separator '@@', LF inside a row", b"1;x\ny;z@@2;p;q@@", s3, reader={"row_separator": "@@"})
    case("5.33", "plain: row_separator '@@', header 1, footer 1, no trailing separator", b"h;h;h@@1;x;z@@2;p;q@@f;f;f", s3,
         reader={"row_separator": "@@", "header_rows": 1, "footer_rows": 1})
    case("5.34", "csv: csv_row_separator '@@'", b'1;"x;y";z@@2;p;q@@', s3, reader={"csv_option": True, "csv_row_separator": "@@"})
    case("5.35", "csv: row_separator '@@' (csv mode reads csv_row_separator instead)", b'1;"x;y";z@@2;p;q@@', s3,
         reader={"csv_option": True, "row_separator": "@@"})
    utf, lat = "caf\u00e9;\u20ac5\n".encode("utf-8"), "caf\u00e9;\u20ac5\n".encode("iso-8859-15")

    def enc(r, w):
        return {"reader": {"encoding": r}, "writer": {"encoding": w}}

    case("5.40", "UTF-8 file, read UTF-8, write UTF-8", utf, s2, **enc("UTF-8", "UTF-8"))
    case("5.41", "ISO-8859-15 file, read ISO-8859-15, write ISO-8859-15", lat, s2, **enc("ISO-8859-15", "ISO-8859-15"))
    case("5.42", "ISO-8859-15 file, read ISO-8859-15, write UTF-8", lat, s2, **enc("ISO-8859-15", "UTF-8"))
    case("5.43", "UTF-8 file, read UTF-8, write ISO-8859-15", utf, s2, **enc("UTF-8", "ISO-8859-15"))
    case("5.44", "UTF-8 file read as ISO-8859-15, written ISO-8859-15", utf, s2, **enc("ISO-8859-15", "ISO-8859-15"))
    case("5.45", "ISO-8859-15 file read as UTF-8, written UTF-8", lat, s2, **enc("UTF-8", "UTF-8"))
    case("5.46", "encoding key absent on both sides, ISO-8859-15 file", lat, s2, drop_reader=("encoding",), drop_writer=("encoding",))
    case("5.47", "encoding key absent on both sides, UTF-8 file", utf, s2, drop_reader=("encoding",), drop_writer=("encoding",))
    cjk = "ok;fine\nx;\u4e2d\u6587\ny;late\n".encode("utf-8")
    case("5.48", "a character the writer's encoding lacks", cjk, s2, **enc("UTF-8", "ISO-8859-15"))
    case("5.49", "control characters, C1 characters and U+FFFD in fields (UTF-8)",
         b"a\x01b\x1fc\x7fd;t\tab\x0bvt\x0cff\n" + "x\u0085y\u009fz;\ufffd!\u00a0\n".encode("utf-8"), s2)
    case("5.50", "ISO-8859-15 read: bytes 0x80, 0x9f, 0xa0", b"a\x80b\x9fc;d\xa0e\n", s2, **enc("ISO-8859-15", "ISO-8859-15"))
    case("5.51", "NUL inside a field, plain", b"ab\x00cd;x\nef;y\n", s2)
    case("5.52", "NUL inside a field, csv", b"ab\x00cd;x\nef;y\n", s2, reader=CSV)
    case("5.53", "encoding names: latin1 on the reader, utf8 on the writer", lat, s2, **enc("latin1", "utf8"))
    case("5.54", "unknown encoding on the reader", lat, s2, **enc("NOPE-1", "UTF-8"))
    case("5.55", "unknown encoding on the writer", utf, s2, **enc("UTF-8", "NOPE-1"))
    bom = b"\xef\xbb\xbf"
    case("5.60", "UTF-8 BOM, plain, first column str", bom + b"abc;x\ndef;y\n", s2)
    case("5.61", "UTF-8 BOM, plain, first column int", bom + b"1;x\n2;y\n", "a:int, b:str")
    case("5.62", "UTF-8 BOM, csv, first column str", bom + b"abc;x\ndef;y\n", s2, reader=CSV)
    case("5.63", "UTF-8 BOM, csv, first column int", bom + b"1;x\n2;y\n", "a:int, b:str", reader=CSV)
    case("5.64", "UTF-8 BOM, csv, first field quoted", bom + b'"abc";x\n', s2, reader=CSV)
    case("5.65", "UTF-8 BOM, plain, python parser (footer_rows 1)", bom + b"abc;x\ndef;y\nf;f\n", s2, reader={"footer_rows": 1})
    case("5.66", "UTF-8 BOM, plain, custom row separator", bom + b"abc;x@@def;y@@", s2, reader={"row_separator": "@@"})
    case("5.67", "UTF-8 BOM file read and written as ISO-8859-15", bom + b"abc;x\n", s2, **enc("ISO-8859-15", "ISO-8859-15"))
    case("5.68", "encoding utf-8-sig on both sides", bom + b"abc;x\n", s2, **enc("utf-8-sig", "utf-8-sig"))


# --------------------------------------------------------------------------- 6
def area6():
    head("6. Rows")
    s3, t3 = "a:str, b:str, c:str", "a:int, b:str, c:float"
    f = b"h1;h2;h3\nH1;H2;H3\n1;x;z\n2;p;q\n3;r;s\nf1;f2;f3\n"
    for i, hr in enumerate((0, 1, 2, "1", 10), 1):
        case(f"6.0{i}", f"header_rows {hr!r}", f, s3, show_held=False, reader={"header_rows": hr})
    case("6.06", "header_rows 2, csv", f, s3, show_held=False, reader={"header_rows": 2, **CSV})
    case("6.07", "header_rows 1 when the first line is blank, plain", b"\nh;h;h\n1;x;z\n", s3, show_held=False, reader={"header_rows": 1})
    case("6.08", "header_rows 1 when the first line is blank, csv", b"\nh;h;h\n1;x;z\n", s3, show_held=False, reader={"header_rows": 1, **CSV})
    case("6.10", "footer_rows 1 (header_rows 2)", f, s3, show_held=False, reader={"header_rows": 2, "footer_rows": 1})
    case("6.11", "footer_rows 2 (header_rows 2)", f, s3, show_held=False, reader={"header_rows": 2, "footer_rows": 2})
    case("6.12", "footer_rows 2 (header_rows 2), csv", f, s3, show_held=False, reader={"header_rows": 2, "footer_rows": 2, **CSV})
    case("6.13", "footer_rows 1, file ends with a blank line, plain", b"1;x;z\n2;p;q\nf;f;f\n\n", s3, show_held=False, reader={"footer_rows": 1})
    case("6.14", "footer_rows 1, file ends with a blank line, csv", b"1;x;z\n2;p;q\nf;f;f\n\n", s3, show_held=False, reader={"footer_rows": 1, **CSV})
    case("6.15", "footer_rows 1, last line has no newline", b"1;x;z\n2;p;q\nf;f;f", s3, show_held=False, reader={"footer_rows": 1})
    case("6.16", "footer_rows 10 (more than the file)", f, s3, show_held=False, reader={"footer_rows": 10})
    for i, lim in enumerate(("2", 2, " 2 ", "0", "-1", "abc", "2.0"), 20):
        case(f"6.{i}", f"limit {lim!r} (header_rows 2)", f, s3, show_held=False, reader={"header_rows": 2, "limit": lim})
    case("6.27", "limit 2, csv", f, s3, show_held=False, reader={"header_rows": 2, "limit": "2", **CSV})
    case("6.28", "limit 2 with footer_rows 2", f, s3, show_held=False, reader={"header_rows": 2, "limit": "2", "footer_rows": 2})
    case("6.29", "limit 2, first data line blank, plain", b"\n1;x;z\n2;p;q\n3;r;s\n", s3, show_held=False, reader={"limit": "2"})
    case("6.30", "limit 2, first data line blank, csv", b"\n1;x;z\n2;p;q\n3;r;s\n", s3, show_held=False, reader={"limit": "2", **CSV})
    case("6.31", "limit 2, first data line is ';;', plain", b";;\n1;x;z\n2;p;q\n3;r;s\n", s3, show_held=False, reader={"limit": "2"})
    e = b"1;x;1.5\n\n;;\n  ; ;\t\n \n2;p;2.5\n"
    case("6.40", "remove_empty_row true, plain", e, t3)
    case("6.41", "remove_empty_row false, plain", e, t3, reader={"remove_empty_row": False})
    case("6.42", "remove_empty_row true, csv", e, t3, reader=CSV)
    case("6.43", "remove_empty_row false, csv", e, t3, reader={"remove_empty_row": False, **CSV})
    case("6.44", "remove_empty_row false, csv, chunked path (check_date true)", e, t3, reader={"remove_empty_row": False, "check_date": True, **CSV})
    case("6.45", "remove_empty_row given as the string 'false'", e, t3, show_held=False, reader={"remove_empty_row": "false"})
    case("6.46", "empty file", b"", t3)
    case("6.47", "header only (header_rows 1)", b"h1;h2;h3\n", t3, reader={"header_rows": 1})
    case("6.48", "last row has no newline", b"1;x;1.5\n2;p;2.5", t3, show_held=False)
    case("6.49", "one blank line, remove_empty_row false, plain", b"1;x;1.5\n\n2;p;2.5\n", t3, reader={"remove_empty_row": False})
    case("6.49b", "one blank line, remove_empty_row false, csv", b"1;x;1.5\n\n2;p;2.5\n", t3, reader={"remove_empty_row": False, **CSV})
    w = b" 1 ; x y ;  2.5 \n2;\tp\t;3\n3;   ;4\n"
    case("6.50", "trim_all false", w, t3)
    case("6.51", "trim_all true", w, t3, reader={"trim_all": True})
    case("6.52", "trim_all true, all-str schema", w, s3, reader={"trim_all": True})
    case("6.53", "trim_all true, csv, quoted spaces", b'" 1 ";" x ";"  "\n', s3, reader={"trim_all": True, **CSV})
    case("6.54", "trim_select b only", w, s3, reader={"trim_select": [{"column": "a", "trim": False}, {"column": "b", "trim": True}, {"column": "c", "trim": False}]})
    case("6.55", "trim_select naming an unknown column", w, s3, reader={"trim_select": [{"column": "nope", "trim": True}]})
    case("6.56", "trim_all true with trim_select all false", w, s3, reader={"trim_all": True, "trim_select": [{"column": "b", "trim": False}]})
    case("6.57", "trim_all given as the string 'false'", w, s3, reader={"trim_all": "false"})
    n = 60
    for label, data, extra in (
            ("short row in the middle, plain", b"1;x;1.5\n2;y\n3;z;3.5\n", {}),
            ("short row first, plain", b"1;x\n2;y;2.5\n3;z;3.5\n", {}),
            ("every row short (2 fields, schema 3), plain", b"1;x\n2;y\n", {}),
            ("row whose last field is empty, plain", b"1;x;1.5\n2;y;\n", {}),
            ("row whose middle field is empty, plain", b"1;;1.5\n2;y;2.5\n", {}),
            ("short row, plain with footer_rows 1 (python parser)", b"1;x;1.5\n2;y\n3;z;3.5\nf;f;f\n", {"footer_rows": 1}),
            ("short row, csv", b"1;x;1.5\n2;y\n3;z;3.5\n", CSV),
            ("every row short, csv", b"1;x\n2;y\n", CSV),
            ("long row in the middle, plain", b"1;x;1.5\n2;y;2.5;EXTRA\n3;z;3.5\n", {}),
            ("long row first, plain", b"1;x;1.5;EXTRA\n2;y;2.5\n3;z;3.5\n", {}),
            ("every row long (4 fields, schema 3), plain", b"1;x;1.5;E1\n2;y;2.5;E2\n", {}),
            ("long row in the middle, plain with footer_rows 1 (python parser)", b"1;x;1.5\n2;y;2.5;EXTRA\n3;z;3.5\nf;f;f\n", {"footer_rows": 1}),
            ("long row in the middle, csv", b"1;x;1.5\n2;y;2.5;EXTRA\n3;z;3.5\n", CSV),
            ("every row long, csv", b"1;x;1.5;E1\n2;y;2.5;E2\n", CSV)):
        for cfn in (False, True):
            case(f"6.{n}", f"{label}, check_fields_num {str(cfn).lower()}", data, t3, reader={**extra, "check_fields_num": cfn})
            n += 1
    s = "a:int, b:str, c:str"
    case("6.90", "short row padded by the python parser, check_fields_num true, str last column", b"1;x;u\n2;y\n3;z;w\nf;f;f\n", s,
         reader={"footer_rows": 1, "check_fields_num": True})
    case("6.91", "short row in csv mode, check_date true, str last column", b"1;x;u\n2;y\n3;z;w\n", s, reader={"check_date": True, **CSV})
    case("6.92", "short row in csv mode, fast path, str last column", b"1;x;u\n2;y\n3;z;w\n", s, reader=CSV)
    case("6.93", "reader csv_option given as the string 'false'", b'1;"x;y";z\n', s3, reader={"csv_option": "false"})
    case("6.94", "short row with a two-character separator (python parser), check_fields_num true, str last column",
         b"1||x||u\n2||y\n3||z||w\n", s, reader={"fieldseparator": "||", "check_fields_num": True})


# --------------------------------------------------------------------------- 7
def area7():
    head("7. Output keys")
    t = "id:int, name:str, amt:float, ok:bool, d:datetime@%Y-%m-%d, m:Decimal#2"
    d = b"1;alice;10.5;true;2024-01-31;1.5\n2;;;;;\n3;c d;3;false;2024-02-01;2\n"
    sc, a, b = "id:int, name:str", b"1;a\n2;b\n", b"3;c\n"

    def w(cid, title, data=a, spec=sc, **kw):
        return case(cid, title, data, spec, show_held=False, **kw)

    w("7.01", "include_header false", d, t)
    w("7.02", "include_header true", d, t, writer={"include_header": True})
    w("7.03", "include_header true, csv_option true", d, t, writer={"include_header": True, **CSV})
    w("7.04", "include_header given as the string 'false'", d, t, writer={"include_header": "false"})
    w("7.05", "csv_option true: which fields are quoted", d, t, writer=CSV)
    seps = [{"os_line_separator": True, "row_separator": "\\r\\n"},
            {"os_line_separator": False, "row_separator": "\\n"},
            {"os_line_separator": False, "row_separator": "\\r\\n"},
            {"os_line_separator": False, "row_separator": "\\r"},
            {"os_line_separator": False, "row_separator": "@@"},
            {"os_line_separator": False, "row_separator": "|\\n"},
            {"os_line_separator": False, "row_separator": ""},
            {"os_line_separator": False, "row_separator": "\\r\\n", "csvrowseparator": "CR"},
            {"os_line_separator": True, "csv_option": True, "csvrowseparator": "CRLF"},
            {"os_line_separator": False, "csv_option": True, "csvrowseparator": "LF"},
            {"os_line_separator": False, "csv_option": True, "csvrowseparator": "CR"},
            {"os_line_separator": False, "csv_option": True, "csvrowseparator": "CRLF"},
            {"os_line_separator": False, "csv_option": True, "csvrowseparator": "\\n"},
            {"os_line_separator": False, "csv_option": True, "csvrowseparator": "\\r\\n"},
            {"os_line_separator": False, "csv_option": True, "csvrowseparator": "lf"},
            {"os_line_separator": False, "csv_option": True, "csvrowseparator": "CRLF", "row_separator": "@@"},
            {"os_line_separator": "false", "row_separator": "\\r\\n"}]
    for i, cfg in enumerate(seps, 10):
        w(f"7.{i}", "row separator keys", writer=cfg)
    w("7.27", "os_line_separator key absent, row_separator CRLF text", writer={"row_separator": "\\r\\n"}, drop_writer=("os_line_separator",))
    ah = {"append": True, "include_header": True}
    x = newdir("append_twice")
    w("7.30", "append true + include_header true, run 1 (file absent)", workdir=x, writer=ah)
    w("7.31", "  run 2 into the same file", data=b, workdir=x, writer=ah)
    x, pre = newdir("append_zero"), {"out.csv": b""}
    w("7.32", "append true + include_header true, existing 0-byte file", workdir=x, pre=pre, writer=ah)
    x, pre = newdir("append_nonl"), {"out.csv": b"old;line-without-newline"}
    w("7.33", "append true, existing file lacks a final newline", workdir=x, pre=pre, writer=ah)
    x, pre = newdir("append_exists"), {"out.csv": b"old;line\n"}
    w("7.34", "append true with file_exist_exception true (baseline)", workdir=x, pre=pre, writer={"append": True})
    x, pre = newdir("append_empty"), {"out.csv": b"old;line\n"}
    w("7.35", "append true, empty input, file exists", data=b"", workdir=x, pre=pre, writer=ah)
    w("7.36", "append true, empty input, file absent", data=b"", writer=ah)
    x, pre = newdir("exists_true"), {"out.csv": b"old;line\n"}
    w("7.40", "file exists, file_exist_exception true", workdir=x, pre=pre)
    x, pre = newdir("exists_absent"), {"out.csv": b"old;line\n"}
    w("7.41", "file exists, file_exist_exception key absent", workdir=x, pre=pre, drop_writer=("file_exist_exception",))
    x, pre = newdir("exists_false"), {"out.csv": b"old;line\nold2;line2\nold3;line3\n"}
    w("7.42", "file exists, file_exist_exception false", workdir=x, pre=pre, writer={"file_exist_exception": False})
    x, pre = newdir("exists_empty"), {"out.csv": b"old;line\n"}
    w("7.43", "file exists, file_exist_exception true, empty input", data=b"", workdir=x, pre=pre)
    x = newdir("mkdir_true")
    w("7.45", "create_directory true, two missing directory levels", workdir=x, writer={"filepath": str(x / "p" / "q" / "out.csv")})
    x = newdir("mkdir_false")
    w("7.46", "create_directory false, missing directory", workdir=x, writer={"filepath": str(x / "p" / "out.csv"), "create_directory": False})
    n = 50
    for deh in (False, True):
        for hdr in (False, True):
            w(f"7.{n}", f"empty input, delete_empty_file {str(deh).lower()}, include_header {str(hdr).lower()}", data=b"",
              writer={"delete_empty_file": deh, "include_header": hdr})
            n += 1
    x, pre = newdir("delete_existing"), {"out.csv": b"old;line\n"}
    w("7.54", "empty input, delete_empty_file true, file exists, file_exist_exception false", data=b"", workdir=x, pre=pre,
      writer={"delete_empty_file": True, "file_exist_exception": False})
    x, pre = newdir("truncate_existing"), {"out.csv": b"old;line\n"}
    w("7.55", "empty input, delete_empty_file false, file exists, file_exist_exception false", data=b"", workdir=x, pre=pre,
      writer={"file_exist_exception": False})
    w("7.56", "empty input, include_header true, csv_option true", data=b"", writer={"include_header": True, **CSV})
    w("7.57", "every row rejected upstream, delete_empty_file true", data=b"x;a\ny;b\n", writer={"delete_empty_file": True})
    w("7.58", "every row rejected upstream, include_header true", data=b"x;a\ny;b\n", writer={"include_header": True})
    a5 = b"1;a\n2;b\n3;c\n4;d\n5;e\n"
    w("7.60", "split true, split_every '2', include_header true", data=a5, writer={"split": True, "split_every": "2", "include_header": True})
    w("7.61", "split true, split_every 5 (exact fit)", data=a5, writer={"split": True, "split_every": 5})
    w("7.62", "split true, split_every 'abc'", data=a5, writer={"split": True, "split_every": "abc"})
    w("7.63", "split true, split_every '0'", data=a5, writer={"split": True, "split_every": "0"})
    w("7.64", "split true, split_every '-2'", data=a5, writer={"split": True, "split_every": "-2"})
    x = newdir("split_dots")
    w("7.65", "split true, file name out.2024.csv", data=a5, workdir=x, writer={"split": True, "split_every": "3", "filepath": str(x / "out.2024.csv")})
    x = newdir("split_noext")
    w("7.66", "split true, file name without extension", data=a5, workdir=x, writer={"split": True, "split_every": "3", "filepath": str(x / "outfile")})
    x, pre = newdir("split_base_exists"), {"out.csv": b"base\n"}
    w("7.67", "split true, base file exists, file_exist_exception true", data=a5, workdir=x, pre=pre, writer={"split": True, "split_every": "2"})
    x, pre = newdir("split_parts_exist"), {"out0.csv": b"old0\n", "out7.csv": b"old7\n"}
    w("7.68", "split true, out0.csv and out7.csv exist, file_exist_exception true", data=a5, workdir=x, pre=pre, writer={"split": True, "split_every": "2"})
    x, pre = newdir("split_append"), {"out0.csv": b"old0\n"}
    w("7.69", "split true, append true, include_header true, out0.csv exists", data=a5, workdir=x, pre=pre,
      writer={"split": True, "split_every": "2", **ah})
    w("7.70", "split true, empty input, include_header true", data=b"", writer={"split": True, "split_every": "2", "include_header": True})
    w("7.75", "writer encoding key absent", data="1;caf\u00e9 \u20ac\n".encode("utf-8"), drop_writer=("encoding",))
    w("7.76", "non-ASCII column name in the header, ISO-8859-15", data=b"1;x\n", spec="id:int, n\u00e9:str",
      writer={"include_header": True, "encoding": "ISO-8859-15"})
    w("7.77", "writer encoding UTF-16", data="1;caf\u00e9\n".encode("utf-8"), writer={"encoding": "UTF-16", "include_header": True})


# --------------------------------------------------------------------------- 8
def area8():
    head("8. Columns")
    rs = "id:int, name:str, d:datetime@%Y-%m-%d, m:Decimal#2, ok:bool"
    d = b"1;alice;2024-01-31;1.5;true\n2;bob;2024-02-01;2;false\n"
    h = {"include_header": True}
    rev = "ok:bool, m:Decimal#2, d:datetime@%Y-%m-%d, name:str, id:int"

    def w(cid, title, data=d, spec=rs, show_held=False, **kw):
        kw.setdefault("writer", h)
        return case(cid, title, data, spec, show_held=show_held, **kw)

    w("8.01", "writer schema.input in the frame's order")
    w("8.02", "writer schema.input in reverse order", wschema=rev)
    w("8.03", "writer schema.output in reverse order", wschema_out=rev)
    w("8.04", "writer schema.input lists only id and name (frame has three more columns)", wschema="id:int, name:str")
    w("8.05", "writer schema.input lists a column the frame lacks", wschema=rs + ", extra:str")
    w("8.06", "writer schema.output lists a column the frame lacks", wschema_out=rs + ", extra:int!")
    w("8.07", "writer schema.output says nullable false for a column holding a null",
      data=b"1;alice;2024-01-31;1.5;true\n2;;;;\n", wschema_out="id:int, name:str, d:datetime!@%Y-%m-%d, m:Decimal#2, ok:bool")
    w("8.10", "reader schema has more columns than the file, plain", data=b"1;alice\n2;bob\n", show_held=True,
      spec="id:int, name:str, n:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2, s:str")
    w("8.11", "reader schema has fewer columns than the file, plain", data=b"1;alice;x;y\n2;bob;x;y\n", spec="id:int, name:str", show_held=True)
    w("8.12", "reader schema has more columns than the file, csv", data=b"1;alice\n2;bob\n", spec="id:int, name:str, s:str", reader=CSV, show_held=True)
    w("8.13", "reader schema has fewer columns than the file, csv", data=b"1;alice;x\n2;bob;x\n", spec="id:int, name:str", reader=CSV, show_held=True)
    w("8.14", "names are positional: schema 'name, id' over a file whose fields are id, name", data=b"1;alice\n2;bob\n", spec="name:str, id:str", show_held=True)
    w("8.15", "no schema on either component", data=b"1;alice\n2;bob\n", spec=[], wschema=[], show_held=True)
    w("8.16", "reader column named errorCode", data=b"1;alice\n2;bob\n", spec="id:int, errorCode:str", show_held=True)


def main():
    environment()
    for area in (area1, area2, area3, area4, area5, area6, area7, area8):
        area()
    out(f"\n{_count[0]} jobs run; all files under {TMP}")


if __name__ == "__main__":
    main()
