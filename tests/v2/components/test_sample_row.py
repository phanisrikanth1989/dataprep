"""Sample row, against v1 on the same job config and bytes."""
import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, reader, writer

SCHEMA = "id:int, name:str"
DATA = b"id;name\n" + b"".join(b"%d;n%d\n" % (n, n) for n in range(1, 13))


def sampled(rejects=True, **config):
    """file -> sample row -> out.csv, and rej.csv for the rows that are not picked."""
    component = {"id": "it", "type": "SampleRow", "config": config,
                 "schema": {"input": columns(SCHEMA), "output": columns(SCHEMA)},
                 "inputs": ["row1"], "outputs": ["row2"]}
    components = [reader(SCHEMA, header_rows=1), component, writer(SCHEMA)]
    flows = [flow("row1", "in", "it"), flow("row2", "it", "out")]
    if rejects:
        component["outputs"].append("row3")
        components.append(writer(SCHEMA, "rej", "rej.csv", ("row3",)))
        flows.append(flow("row3", "it", "rej", "reject"))
    return job(components, flows)


def ids(run, name="out.csv"):
    return [line.split(";")[0] for line in run.files[name].decode().splitlines()[1:]]


def same(tmp_path, data=DATA, **kwargs):
    run = assert_matches_v1(sampled(**kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    return run


def test_rows_are_picked_by_their_place_and_the_others_are_rejects(tmp_path):
    run = same(tmp_path, range="1,5,10..20")
    assert ids(run) == ["1", "5", "10", "11", "12"]
    assert ids(run, "rej.csv") == ["2", "3", "4", "6", "7", "8", "9"]


@pytest.mark.parametrize("picked, kept", [
    ("3", ["3"]), ("2..4", ["2", "3", "4"]), (" 4 , 2..3 ,, 4", ["2", "3", "4"]), ("50", []), ("11..99", ["11", "12"]),
])
def test_range_forms(tmp_path, picked, kept):
    assert ids(same(tmp_path, range=picked)) == kept


def test_picked_rows_alone_when_no_flow_takes_the_others(tmp_path):
    assert ids(same(tmp_path, rejects=False, range="2")) == ["2"]


def test_no_rows_in(tmp_path):
    assert ids(same(tmp_path, b"id;name\n", range="1")) == []


@pytest.mark.parametrize("picked, said", [
    ("a", "'a' is not a row's place"), ("3..1", "3..1 runs backwards"), ("0", "rows are counted from 1"),
    ("1..2..3", "'1..2..3' is not a row's place"), ("", "names no row"), ("  ", "names no row"),
])
def test_range_that_cannot_be_read_refuses_the_job(picked, said):
    with pytest.raises(JobRefusedError, match=said):
        load_job(sampled(range=picked))


def test_range_is_needed():
    with pytest.raises(JobRefusedError, match="range"):
        load_job(sampled())


# ------------------------------------------------------------------
# What a second reader of this component found (ticket 62)
# ------------------------------------------------------------------

@pytest.mark.parametrize("picked, kept", [("+3", ["3"]), ("1_0", ["10"]), (",", []), (" 2 .. 3 ", ["2", "3"])])
def test_number_is_read_as_python_reads_one_which_is_how_v1_reads_it(tmp_path, picked, kept):
    assert ids(same(tmp_path, range=picked)) == kept


@pytest.mark.parametrize("picked, said", [("²", "is not a row's place"), (None, "range"), (5, "range")])
def test_more_ranges_that_refuse_the_job_with_words_of_its_own(picked, said):
    with pytest.raises(JobRefusedError, match=said) as caught:
        load_job(sampled(range=picked))
    assert "invalid literal" not in str(caught.value) and "NoneType" not in str(caught.value)


def test_die_on_error_is_the_engines_as_on_every_component(tmp_path):
    made = sampled(rejects=False, range="1..5", die_on_error=False)
    made["components"][1]["schema"]["output"][1]["nullable"] = False
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and len(run.files["out.csv"].splitlines()) == 6
