"""Stand-in components and helpers the engine tests share."""
from pathlib import Path

import polars as pl

from src.v2.components.base import Eager, Sink, Source, Transform, Write
from src.v2.components.registry import Registry
from src.v2.engine import run_job
from src.v2.expressions import translate
from src.v2.job.keys import EXPRESSION, Key


class Rows(Source):
    """Rows written in the config, as a lazy frame."""

    names = ("rows",)
    keys = (Key("data", type=dict, required=True),)

    def read(self):
        return {"main": pl.LazyFrame(self.config["data"])}


class FromFile(Source):
    names = ("from_file",)
    keys = (Key("path", required=True),)

    def read(self):
        return {"main": pl.scan_csv(self.config["path"])}


class Add(Transform):
    names = ("add",)
    keys = (Key("amount", type=int, default=1), Key("column", default="n"))

    def build(self, inputs):
        (frame,) = inputs.values()
        return {"main": frame.with_columns(pl.col(self.config["column"]) + self.config["amount"])}


class Split(Transform):
    """Rows above a limit leave by main, the rest by reject."""

    names = ("split",)
    keys = (Key("limit", type=int, required=True),)
    outputs = {"main": ("flow", "main", "filter"), "reject": ("reject",)}

    def build(self, inputs):
        (frame,) = inputs.values()
        flagged = frame.with_columns((pl.col("n") > self.config["limit"]).alias("__keep"))
        return {
            "main": flagged.filter(pl.col("__keep")).drop("__keep"),
            "reject": flagged.filter(~pl.col("__keep")).drop("__keep"),
        }


class Stack(Transform):
    """Its inputs one after another, each row tagged with the flow it came by."""

    names = ("stack",)
    max_inputs = None

    def build(self, inputs):
        tagged = [frame.with_columns(pl.lit(name).alias("via")) for name, frame in inputs.items()]
        return {"main": pl.concat(tagged)}


class Save(Sink):
    names = ("save",)
    keys = (Key("path", required=True),)

    def write(self, frame):
        return Write(
            path=self.config["path"],
            sink=lambda path: frame.sink_csv(path, lazy=True),
            rows=frame.select(pl.len()),
        )


class Peek(Eager):
    """Remembers the frame it was handed and passes it on."""

    names = ("peek",)
    seen = []

    def run(self, inputs):
        (frame,) = inputs.values()
        Peek.seen.append(frame)
        return {"main": frame}


class SetContext(Eager):
    """Puts its first row into the context, as context_load does."""

    names = ("set_context",)
    min_inputs = 1
    sets_context = True

    def run(self, inputs):
        (frame,) = inputs.values()
        self.context.update(frame.row(0, named=True))
        return {}


class Mark(Source):
    """Notes that it was built, in the order that happened, and yields one row."""

    names = ("mark",)
    keys = (Key("name", required=True),)
    ran = []

    def read(self):
        Mark.ran.append(self.config["name"])
        return {"main": pl.LazyFrame({"n": [1]})}


class Boom(Source):
    """Fails as soon as it is built."""

    names = ("boom",)
    keys = (Key("why", default="boom"),)

    def read(self):
        raise RuntimeError(self.config["why"])


class Guard(Transform):
    """Passes rows on and fails the subjob afterwards when any n is negative."""

    names = ("guard",)

    def build(self, inputs):
        (frame,) = inputs.values()
        self.check(
            frame.select((pl.col("n") < 0).sum().alias("bad")),
            lambda found: f"{found.item()} negative value(s)" if found.item() else None,
        )
        return {"main": frame}


class Glance(Transform):
    """Passes rows on untouched and remembers the first two once the pass has run."""

    names = ("glance",)
    seen = []

    def build(self, inputs):
        (frame,) = inputs.values()
        self.tap(frame.head(2), Glance.seen.append)
        return {"main": frame}


class Either(Transform):
    """Lazy by default; asks for real rows when its config says so."""

    names = ("either",)
    keys = (Key("rows_in_hand", type=bool, default=False),)
    handed = []

    def needs_rows(self):
        return self.config["rows_in_hand"]

    def build(self, inputs):
        (frame,) = inputs.values()
        Either.handed.append(type(frame).__name__)
        return {"main": frame}

    def run(self, inputs):
        (frame,) = inputs.values()
        Either.handed.append(type(frame).__name__)
        return {"main": frame}


class Through(Transform):
    """Passes rows on untouched; has a reject output and may tolerate errors."""

    names = ("through",)
    keys = (Key("die_on_error", type=bool, default=True),)
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}

    def build(self, inputs):
        (frame,) = inputs.values()
        return {"main": frame, "reject": frame.clear()}


class Calc(Transform):
    """Replaces column n by the value of an expression over the row."""

    names = ("calc",)
    keys = (Key("expression", type=EXPRESSION, required=True),)

    def build(self, inputs):
        (frame,) = inputs.values()
        value = translate(self.config["expression"], self.row_scope(frame.collect_schema(), "row1"))
        return {"main": frame.with_columns(value.cast(pl.Int64).alias("n"))}


class Scratch(Source):
    """Asks the run for a scratch file and reads it back."""

    names = ("scratch",)
    made = []

    def read(self):
        path = self.run_context.temp_path(".csv")
        Path(path).write_text("n\n7\n")
        Scratch.made.append(path)
        return {"main": pl.scan_csv(path)}


REGISTRY = Registry()
for _cls in (Rows, FromFile, Add, Split, Stack, Save, Peek, SetContext, Mark, Boom, Guard, Glance, Either, Through, Calc, Scratch):
    REGISTRY.register(_cls)


def job(components, flows, **more):
    made = {
        "job_name": "t",
        "components": [{"id": cid, "type": ctype, "config": config} for cid, ctype, config in components],
        "flows": [
            {"name": name, "from": source, "to": target, "type": kind}
            for name, source, target, kind in flows
        ],
    }
    made.update(more)
    return made


def schema_of(*columns):
    """A schema block from (name, type) or (name, type, nullable) tuples."""
    return {"output": [
        {"name": column[0], "type": column[1], "nullable": column[2] if len(column) > 2 else True}
        for column in columns
    ]}


def run(job_config, **kwargs):
    return run_job(job_config, registry=REGISTRY, **kwargs)


def lines(path):
    return Path(path).read_text().splitlines()
