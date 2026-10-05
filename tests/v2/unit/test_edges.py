"""Corners of the core: malformed job configs, odd values, things that fail late."""
import datetime as dt
import runpy
import sys
from decimal import Decimal

import polars as pl
import pytest

from src.v2.cli import main
from src.v2.components.base import Sink, Source, Transform, Write
from src.v2.components.registry import Registry
from src.v2.engine import run_job
from src.v2.engine.conditions import evaluate
from src.v2.errors import ConfigurationError, JobRefusedError
from src.v2.files import as_utf8, codec_name
from src.v2.job.keys import Key, normalize_config
from src.v2.job.loader import load_job as read_job
from src.v2.job.model import Column
from src.v2.types import conform, to_text

from .kit import REGISTRY, job, lines, run, schema_of


def refusals(job_config):
    with pytest.raises(JobRefusedError) as caught:
        read_job(job_config, registry=REGISTRY)
    return [(refusal.key, refusal.reason) for refusal in caught.value.report]


# ------------------------------------------------------------------
# Job configs of the wrong shape
# ------------------------------------------------------------------

BASE = [("in", "rows", {"data": {"n": [1]}})]


@pytest.mark.parametrize(
    "change, key",
    [
        ({"components": ["nope"]}, "components[0]"),
        ({"flows": ["nope"]}, "flows[0]"),
        ({"triggers": ["nope"]}, "triggers[0]"),
    ],
)
def test_entry_that_is_not_an_object_is_refused(change, key):
    made = job(BASE, [])
    made.update(change)
    assert (key, "expected an object") in refusals(made)


@pytest.mark.parametrize(
    "schema, key",
    [
        ("nope", "schema"),
        ({"output": "nope"}, "schema.output"),
        ({"output": ["nope"]}, "schema.output[0]"),
        ({"inputs": ["nope"]}, "schema.inputs"),
        ({"output": [{"name": "a", "type": "money"}]}, "schema.output[0].type"),
    ],
)
def test_schema_of_the_wrong_shape_is_refused(schema, key):
    made = job(BASE, [])
    made["components"][0]["schema"] = schema
    assert key in [found for found, _ in refusals(made)]


def test_schema_may_be_a_plain_list_of_output_columns():
    made = job(BASE, [])
    made["components"][0]["schema"] = [{"name": "n", "type": "int"}]
    assert [column.name for column in read_job(made, registry=REGISTRY).components["in"].schema] == ["n"]


@pytest.mark.parametrize(
    "value, type_name, expected",
    [("1.5", "float", 1.5), ("1.10", "Decimal", Decimal("1.10")), (False, "bool", False)],
)
def test_context_value_types(value, type_name, expected):
    made = job(BASE, [], context={"v": {"value": value, "type": type_name}})
    assert read_job(made, registry=REGISTRY).context["v"] == expected


@pytest.mark.parametrize("value, type_name", [(True, "int"), ("maybe", "bool"), ("x", "float")])
def test_context_value_that_does_not_fit_is_refused(value, type_name):
    made = job(BASE, [], context={"v": {"value": value, "type": type_name}})
    assert [key for key, _ in refusals(made)] == ["context.v"]


# ------------------------------------------------------------------
# Config values
# ------------------------------------------------------------------

def checked(key, value, **kwargs):
    config, found = normalize_config({key.name: value}, (key,), "here", **kwargs)
    return config.get(key.name), [refusal.reason for refusal in found]


@pytest.mark.parametrize("value, expected", [(2, 2.0), (2.5, 2.5), (" 2.5 ", 2.5), ("", None)])
def test_number_key_takes_numbers_and_numbers_as_text(value, expected):
    assert checked(Key("ratio", type=float), value) == (expected, [])


@pytest.mark.parametrize(
    "key, value, said",
    [
        (Key("ratio", type=float), True, "expected a number"),
        (Key("ratio", type=float), "abc", "expected a number"),
        (Key("flag", type=bool), "maybe", "expected true or false"),
        (Key("name"), 5, "expected text"),
        (Key("items", type=list), {"a": 1}, "expected a list"),
        (Key("fields", type=dict), [1], "expected an object"),
    ],
)
def test_value_of_the_wrong_kind_is_refused(key, value, said):
    _, found = checked(key, value)
    assert len(found) == 1 and found[0].startswith(said)


def test_key_declared_with_an_unknown_type_is_reported_not_hidden():
    _, found = checked(Key("x", type=set), 1)
    assert found == ["key 'x' declares an unknown type <class 'set'>"]


def test_plain_list_items_are_expanded_and_have_their_context_resolved():
    key = Key("names", type=list, item_convert=lambda item: item.strip() if isinstance(item, str) else item)
    value, found = checked(key, [" a ", "${context.b}"], resolve=lambda text: text.replace("${context.b}", "B"))
    assert (value, found) == (["a", "B"], [])


# ------------------------------------------------------------------
# The registry and the command line
# ------------------------------------------------------------------

def test_component_without_a_name_cannot_be_registered():
    class Nameless(Transform):
        pass

    with pytest.raises(ValueError, match="declares no names"):
        Registry().register(Nameless)


def test_two_components_cannot_share_a_name():
    class One(Transform):
        names = ("same",)

    class Two(Transform):
        names = ("same",)

    registry = Registry()
    registry.register(One)
    registry.register(One)
    with pytest.raises(ValueError, match="already registered to One"):
        registry.register(Two)
    assert registry.names() == ["same"]


def test_command_line_help_and_misuse(capsys):
    assert main(["--help"]) == 0
    assert main([]) == 2
    capsys.readouterr()


def test_module_can_be_run_as_a_program(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["src.v2", "--help"])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("src.v2", run_name="__main__")
    assert stopped.value.code == 0
    assert "job_config" in capsys.readouterr().out


# ------------------------------------------------------------------
# RunIf conditions
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "condition, expected",
    [
        ('((Integer)globalMap.get("word")) == 0', True),
        ('((Double)globalMap.get("word")) == 0', True),
        ('((String)globalMap.get("number")) == "7"', True),
        ('((Date)globalMap.get("number")) == 7', True),
        ('((Boolean)globalMap.get("number"))', True),
    ],
)
def test_casts_that_do_not_fit_fall_back_as_in_v1(condition, expected):
    assert evaluate(condition, {}, {"word": "OK", "number": 7}) is expected


# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------

def test_unknown_encoding_is_named():
    with pytest.raises(ConfigurationError, match="unknown encoding: NOPE-1"):
        codec_name("NOPE-1")


@pytest.mark.parametrize("encoding", ["UTF-32", "cp037"])
def test_file_in_an_encoding_unlike_ascii_is_read_through_a_copy(tmp_path, encoding):
    from src.v2.engine.context import RunContext

    path = tmp_path / "in.txt"
    path.write_bytes("plain ascii\n".encode(encoding))
    run_context = RunContext("t", {})
    copy = as_utf8(str(path), encoding, run_context)
    assert copy != str(path)
    with open(copy, "rb") as handle:
        assert handle.read().decode("utf-8").lstrip("﻿") == "plain ascii\n"
    run_context.cleanup()
    run_context.cleanup()


def test_ascii_file_declared_latin_is_read_in_place(tmp_path):
    from src.v2.engine.context import RunContext

    path = tmp_path / "in.txt"
    path.write_bytes(b"plain ascii\n")
    assert as_utf8(str(path), "ISO-8859-15", RunContext("t", {})) == str(path)


# ------------------------------------------------------------------
# Values written as text, and schemas
# ------------------------------------------------------------------

def test_text_dates_and_times_as_text():
    frame = pl.DataFrame({"s": ["x"], "d": [dt.date(2024, 1, 31)], "t": [dt.time(10, 11, 12)]})
    out = frame.select(
        to_text(pl.col("s"), pl.String), to_text(pl.col("d"), pl.Date), to_text(pl.col("t"), pl.Time),
        to_text(pl.col("d"), pl.Date, Column("d", "date", date_pattern="%d/%m/%Y")).alias("d2"),
    )
    assert out.row(0) == ("x", "2024-01-31", "10:11:12", "31/01/2024")


def reshaped(data, schema, column):
    frame, _ = conform(pl.LazyFrame(data, schema=schema), [column])
    return frame.collect()[column.name].to_list()


def test_values_of_another_kind_are_turned_into_the_declared_type():
    inf = float("inf")
    assert reshaped({"v": [1.9, inf, None]}, {"v": pl.Float64}, Column("v", "int")) == [1, None, None]
    assert reshaped({"v": [True, False]}, {"v": pl.Boolean}, Column("v", "int")) == [1, 0]
    assert reshaped({"v": [Decimal("2.50")]}, {"v": pl.Decimal(38, 2)}, Column("v", "float")) == [2.5]
    assert reshaped({"v": [2, 0, None]}, {"v": pl.Int64}, Column("v", "bool")) == [True, False, None]
    assert reshaped({"v": ["yes", "0", "x"]}, {"v": pl.String}, Column("v", "bool")) == [True, False, None]
    assert reshaped({"v": [Decimal("2.50")]}, {"v": pl.Decimal(38, 2)}, Column("v", "Decimal")) == [Decimal("2.50")]
    assert reshaped({"v": [2, 3]}, {"v": pl.Int64}, Column("v", "Decimal", precision=2)) == [Decimal("2.00"), Decimal("3.00")]
    assert reshaped({"v": [dt.date(2024, 1, 31)]}, {"v": pl.Date}, Column("v", "datetime")) == [dt.datetime(2024, 1, 31)]
    assert reshaped({"v": [dt.datetime(2024, 1, 31, 5)]}, {"v": pl.Datetime("us")}, Column("v", "date")) == [dt.date(2024, 1, 31)]
    assert reshaped({"v": [7]}, {"v": pl.Int64}, Column("v", "int", precision=2)) == [7]


# ------------------------------------------------------------------
# Things that fail while a job runs
# ------------------------------------------------------------------

class NoOutput(Transform):
    names = ("no_output",)

    def build(self, inputs):
        return {}


class Picky(Transform):
    names = ("picky",)

    def problems(self):
        return ["mode: cannot be used here"]

    def build(self, inputs):
        return dict(inputs)


class BadTap(Transform):
    names = ("bad_tap",)

    def build(self, inputs):
        (frame,) = inputs.values()

        def explode(rows):
            raise RuntimeError("tap went wrong")

        self.tap(frame.head(1), explode)
        return {"main": frame}


class Fragile(Sink):
    """Writes, then fails when told the row count."""

    names = ("fragile",)
    keys = (Key("path", required=True), Key("append", type=bool, default=False))

    def write(self, frame):
        def finish(rows):
            if not self.config["append"]:
                raise RuntimeError("could not finish")

        return Write(path=self.config["path"], sink=lambda path: frame.sink_csv(path, include_header=False, lazy=True),
                     rows=frame.select(pl.len()), append=self.config["append"], finish=finish)


class Lying(Source):
    """Promises a number column and delivers text that is not one."""

    names = ("lying",)

    def read(self):
        return {"main": pl.LazyFrame({"n": ["1", "x"]}).with_columns(pl.col("n").cast(pl.Int64))}


EDGE = Registry()
for _cls in list(REGISTRY.classes()) + [NoOutput, Picky, BadTap, Fragile, Lying]:
    EDGE.register(_cls)


def edge(job_config, checked=True):
    if checked:
        return run_job(job_config, registry=EDGE)
    return run_job(read_job(job_config, registry=EDGE), registry=EDGE)


def simple(middle, tmp_path, sink=("out", "save", None)):
    out = tmp_path / "out.csv"
    sink_id, sink_type, sink_config = sink
    return job(
        [("in", "rows", {"data": {"n": [1, 2]}}), middle, (sink_id, sink_type, sink_config or {"path": str(out)})],
        [("r1", "in", middle[0], "flow"), ("r2", middle[0], sink_id, "flow")],
    ), out


def test_component_that_returns_no_frame_for_a_wired_output_fails(tmp_path):
    made, _ = simple(("x", "no_output", {}), tmp_path)
    result = edge(made)
    assert result.failed_component == "x" and "produced no 'main' output for flow 'r2'" in result.error


def test_config_problem_is_refused_at_load_and_fails_a_job_run_unchecked(tmp_path):
    made, _ = simple(("x", "picky", {}), tmp_path)
    with pytest.raises(JobRefusedError) as caught:
        edge(made)
    assert "mode: cannot be used here" in caught.value.report.format()
    result = edge(made, checked=False)
    assert result.failed_component == "x" and result.error == "mode: cannot be used here"


def test_tap_that_raises_fails_its_component(tmp_path):
    made, out = simple(("x", "bad_tap", {}), tmp_path)
    result = edge(made)
    assert result.failed_component == "x" and result.error == "tap went wrong"
    assert not out.exists()


def test_failure_after_the_file_is_in_place_is_blamed_on_the_sink(tmp_path):
    made, _ = simple(("x", "add", {}), tmp_path, sink=("out", "fragile", {"path": str(tmp_path / "f.csv")}))
    result = edge(made)
    assert result.failed_component == "out" and result.error == "could not finish"


def test_default_placement_appends_to_an_existing_file(tmp_path):
    target = tmp_path / "f.csv"
    target.write_text("0\n")
    made, _ = simple(("x", "add", {}), tmp_path, sink=("out", "fragile", {"path": str(target), "append": True}))
    assert edge(made).status == "success"
    assert lines(target) == ["0", "2", "3"]


def test_data_problem_is_blamed_on_the_component_whose_output_cannot_be_computed(tmp_path):
    made = job([("in", "lying", {}), ("add", "add", {}), ("out", "save", {"path": str(tmp_path / "o.csv")})],
               [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")])
    result = edge(made)
    assert result.status == "failed" and result.failed_component == "in"


def test_column_that_may_not_be_missing_and_never_is_passes(tmp_path):
    made, out = simple(("x", "through", {}), tmp_path)
    made["components"][1]["schema"] = schema_of(("n", "int", False))
    assert run(made).status == "success"
    assert lines(out) == ["n", "1", "2"]


def test_reject_output_is_put_in_its_declared_shape(tmp_path):
    rejected = tmp_path / "rej.csv"
    made = job(
        [("in", "rows", {"data": {"n": [1, None], "s": ["a", "b"]}}), ("x", "through", {"die_on_error": False}),
         ("out", "save", {"path": str(tmp_path / "o.csv")}), ("rej", "save", {"path": str(rejected)})],
        [("r1", "in", "x", "flow"), ("r2", "x", "out", "flow"), ("r3", "x", "rej", "reject")],
    )
    made["components"][1]["schema"] = {
        "output": [{"name": "n", "type": "int", "nullable": False}, {"name": "s", "type": "str"}],
        "reject": [{"name": "errorMessage", "type": "str"}, {"name": "s", "type": "str", "nullable": False}],
    }
    assert run(made).status == "success"
    assert lines(rejected) == ["errorMessage,s,n,errorCode", "Column 'n': non-nullable column has null,b,,SCHEMA_VIOLATION"]
