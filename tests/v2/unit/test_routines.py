"""Routines: Python modules of functions that take and return Polars expressions."""
import polars as pl
import pytest

from src.v2.engine.routines import load_routines
from src.v2.errors import ConfigurationError, JobRefusedError
from src.v2.expressions import Scope, translate

from .kit import job, lines, run, schema_of

FEES = '''
import polars as pl

RATE = 0.1


def with_fee(amount, rate=RATE):
    return amount * (1 + rate)


def shout(text):
    return text.str.to_uppercase() + pl.lit("!")


def slow(value):
    return value.map_elements(lambda v: v, return_dtype=pl.Int64)


def _private(value):
    return value
'''


@pytest.fixture
def routines_dir(tmp_path):
    folder = tmp_path / "routines"
    folder.mkdir()
    (folder / "fees.py").write_text(FEES)
    (folder / "string_tools.py").write_text("def twice(text):\n    return text + text\n")
    (folder / "_skipped.py").write_text("def nope(x):\n    return x\n")
    return folder


def config(folder, **more):
    made = {"enabled": True, "routines_dir": str(folder)}
    made.update(more)
    return made


def test_each_module_is_named_as_v1_names_it(routines_dir):
    loaded = load_routines(config(routines_dir))
    assert sorted(loaded) == ["Fees", "StringTools"]
    assert sorted(loaded["Fees"]) == ["shout", "slow", "with_fee"]


def test_nothing_is_loaded_unless_routines_are_enabled(routines_dir):
    assert load_routines(None) == {}
    assert load_routines({"enabled": False, "routines_dir": str(routines_dir)}) == {}


def test_routine_the_job_requires_but_is_not_there_is_an_error(routines_dir):
    with pytest.raises(ConfigurationError, match="Missing"):
        load_routines(config(routines_dir, routines=["Fees", "Missing"]))


def test_folder_that_does_not_exist_is_an_error(tmp_path):
    with pytest.raises(ConfigurationError, match="nowhere"):
        load_routines(config(tmp_path / "nowhere"))


def test_module_that_cannot_be_imported_is_an_error(routines_dir):
    (routines_dir / "broken.py").write_text("def oops(:\n")
    with pytest.raises(ConfigurationError, match="broken.py"):
        load_routines(config(routines_dir))


def test_expression_calls_a_routine_on_columns(routines_dir):
    scope = Scope.for_rows({"row1": {"amount": pl.Float64, "name": pl.String}}, bare="row1",
                           routines=load_routines(config(routines_dir)))
    frame = pl.DataFrame({"amount": [100.0], "name": ["ab"]})
    out = frame.select(
        translate("routines.Fees.with_fee(row1.amount, 0.5)", scope).alias("fee"),
        translate("Fees.shout(name)", scope).alias("loud"),
        translate("StringTools.twice(row1.name)", scope).alias("twice"),
    )
    assert out.row(0) == (150.0, "AB!", "abab")


def test_job_loads_its_routines_from_python_config(tmp_path, routines_dir):
    out = tmp_path / "out.csv"
    made = job(
        [("in", "rows", {"data": {"n": [1, 2]}}), ("calc", "calc", {"expression": "Fees.with_fee(n, 1)"}),
         ("out", "save", {"path": str(out)})],
        [("r1", "in", "calc", "flow"), ("r2", "calc", "out", "flow")],
        python_config=config(routines_dir),
    )
    assert run(made).status == "success"
    assert lines(out) == ["n", "2", "4"]


def test_routine_that_works_row_by_row_refuses_the_job(tmp_path, routines_dir):
    made = job(
        [("in", "rows", {"data": {"n": [1]}}), ("calc", "calc", {"expression": "Fees.slow(n)"}),
         ("out", "save", {"path": str(tmp_path / "o.csv")})],
        [("r1", "in", "calc", "flow"), ("r2", "calc", "out", "flow")],
        python_config=config(routines_dir),
    )
    made["components"][0]["schema"] = schema_of(("n", "int"))
    with pytest.raises(JobRefusedError) as caught:
        run(made)
    assert "row by row" in caught.value.report.format()
