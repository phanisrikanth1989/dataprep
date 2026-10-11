"""Split row, against v1 on the same job config and bytes."""
import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import through

SCHEMA = "id:int, jan:int, feb:int, note:str"
DATA = b"id;jan;feb;note\n1;100;200;a\n2;;50;\n3;7;8;c\n"
MONTHS = [{"id": "row1.id", "month": '"Jan"', "amount": "row1.jan"},
          {"id": "row1.id", "month": "'Feb'", "amount": "row1.feb"}]


def split(mapping, out="id:int, month:str, amount:int", schema=SCHEMA, **config):
    return through({"type": "SplitRow", "config": {"col_mapping": mapping, **config}}, schema, out)


def same(tmp_path, mapping, data=DATA, **kwargs):
    run = assert_matches_v1(split(mapping, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    return run.files["out.csv"].decode().splitlines()[1:]


def test_each_row_gives_one_row_for_each_group_in_the_order_of_the_groups(tmp_path):
    assert same(tmp_path, MONTHS) == ["1;Jan;100", "1;Feb;200", "2;Jan;", "2;Feb;50", "3;Jan;7", "3;Feb;8"]


def test_numbers_written_in_a_group_are_numbers(tmp_path):
    mapping = [{"id": "row1.id", "n": "42", "f": "1.5"}, {"id": "row1.id", "n": "-7", "f": "2"}]
    assert same(tmp_path, mapping, out="id:int, n:int, f:float")[:2] == ["1;42;1.5", "1;-7;2.0"]


def test_what_is_neither_a_column_nor_a_literal_is_handed_on_as_written(tmp_path):
    mapping = [{"id": "row1.id", "x": "row1.nope", "y": "something else", "z": "jan"}]
    assert same(tmp_path, mapping, out="id:int, x:str, y:str, z:str")[0] == "1;row1.nope;something else;jan"


def test_column_is_named_after_any_flow(tmp_path):
    assert same(tmp_path, [{"id": "whatever.id", "note": "x.note"}], out="id:int, note:str") == ["1;a", "2;", "3;c"]


def test_group_that_leaves_a_column_out_has_nothing_there(tmp_path):
    mapping = [{"id": "row1.id", "note": "row1.note"}, {"id": "row1.id"}]
    assert same(tmp_path, mapping, out="id:int, note:str") == ["1;a", "1;", "2;", "2;", "3;c", "3;"]


def test_column_of_text_and_numbers_is_written_as_each_stands(tmp_path):
    mapping = [{"v": "row1.id"}, {"v": '"x"'}]
    assert same(tmp_path, mapping, out="v:str")[:2] == ["1", "x"]


def test_no_rows_in_gives_no_rows(tmp_path):
    assert same(tmp_path, MONTHS, b"id;jan;feb;note\n") == []


def test_no_groups_gives_no_rows(tmp_path):
    assert same(tmp_path, []) == []


def test_failure_after_it_still_names_the_source_row(tmp_path):
    from src.v2 import run_job
    import os
    made = split([{"id": "row1.id", "amount": "row1.note"}], out="id:int!, amount:str")
    made["components"][0]["schema"]["output"][0]["key"] = True
    (tmp_path / "in.csv").write_bytes(b"id;jan;feb;note\n1;1;1;a\n;2;2;b\n")
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "failed" and "the row is line 3 of in.csv" in result.error


@pytest.mark.parametrize("mapping, said", [("x", "col_mapping"), ([["a"]], "col_mapping")])
def test_mapping_of_the_wrong_shape_refuses_the_job(mapping, said):
    with pytest.raises(JobRefusedError, match=said):
        load_job(split(mapping))


def test_mapping_is_needed():
    made = split([])
    del made["components"][1]["config"]["col_mapping"]
    with pytest.raises(JobRefusedError, match="col_mapping"):
        load_job(made)


def test_number_written_in_a_group_is_a_number_also_where_the_column_is_text(tmp_path):
    # 1.50 is the number 1.5, and 007 the number 7, before the column's type is looked at.
    assert same(tmp_path, [{"v": "1.50", "w": "007"}], out="v:str, w:str")[0] == "1.5;7"


# ------------------------------------------------------------------
# What a second reader of this component found (ticket 62)
# ------------------------------------------------------------------

KINDS = "id:int, d:datetime@%Y-%m-%d, s:str, b:bool, m:Decimal#2"
KINDS_DATA = b"id;d;s;b;m\n1;2024-01-31;x;true;1.50\n2;2024-02-01;y;false;2.00\n"


def kinds(tmp_path, mapping, out):
    return same(tmp_path, mapping, KINDS_DATA, schema=KINDS, out=out)


def test_date_beside_a_date_written_as_text_stays_a_date(tmp_path):
    got = kinds(tmp_path, [{"v": "r.d"}, {"v": "'2024-03-01'"}], "v:datetime@%Y-%m-%d")
    assert got == ["2024-01-31", "2024-03-01", "2024-02-01", "2024-03-01"]


@pytest.mark.parametrize("mapping, got", [
    ([{"v": "r.d"}, {"v": "r.s"}], ["2024-01-31 00:00:00", "x"]),
    ([{"v": "r.d"}, {"v": "r.id"}], ["2024-01-31 00:00:00", "1"]),
    ([{"v": "r.b"}, {"v": "r.s"}], ["True", "x"]),
    ([{"v": "r.b"}, {"v": "r.id"}], ["True", "1"]),
    ([{"v": "r.m"}, {"v": "r.id"}], ["1.50", "1"]),
    ([{"v": "r.m"}, {"v": "'z'"}], ["1.50", "z"]),
], ids=["date and text", "date and number", "true and text", "true and number", "Decimal and number", "Decimal and text"])
def test_column_made_of_values_of_several_kinds_holds_each_as_it_is_written(tmp_path, mapping, got):
    assert kinds(tmp_path, mapping, "v:str")[:2] == got


def test_whole_and_fractional_numbers_together_are_floats(tmp_path):
    assert same(tmp_path, [{"v": "row1.id"}, {"v": "2.5"}], out="v:str")[:2] == ["1.0", "2.5"]


def test_die_on_error_is_the_engines_as_on_every_component(tmp_path):
    # The row that misses the value is dropped on both. (v1 writes the whole numbers beside it as 100.0.)
    from tests.v2 import answer_key
    made = split([{"id": "row1.jan", "note": "row1.note"}], out="id:int!, note:str", die_on_error=False)
    runs = [answer_key.run_job(made, {"in.csv": DATA}, tmp_path / name, runner)
            for name, runner in (("v1", answer_key.run_v1), ("v2", answer_key.run_v2))]
    assert [run.files["out.csv"].decode().splitlines()[1:] for run in runs] == [["100.0;a", "7.0;c"], ["100;a", "7;c"]]


def test_no_groups_counts_no_rows_as_in_v1(tmp_path):
    from src.v2 import run_job
    from tests.v2.answer_key import run_job as in_folder, run_v1
    counted = {}
    made = split([])
    in_folder(made, {"in.csv": DATA}, tmp_path / "v1", lambda job: counted.update(v1=run_v1(job)["it"]))
    in_folder(made, {"in.csv": DATA}, tmp_path / "v2", lambda job: counted.update(v2=run_job(job, row_counts=True).counts["it"]))
    assert counted["v2"] == counted["v1"] == {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}
