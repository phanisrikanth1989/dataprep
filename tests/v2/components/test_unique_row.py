"""Unique row, against v1 on the same job config and bytes."""
import json
import os
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.components.registry import REGISTRY, Registry
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1
from tests.v2.unit import kit as stand_ins

from .kit import columns, flow, job, reader, writer

SCHEMA = "id:int, name:str, amt:float"
ROWS = b"1;a;1.5\n2;b;2.5\n3;A;3.5\n4;a;4.5\n5;c;5.5\n6;B;6.5\n7;a;7.5\n"
HEADER = b"id;name;amt\n"
BY_NAME = [{"column": "name", "case_sensitive": True}]
ANY_CASE = [{"column": "name", "case_sensitive": False}]


def dedupe(config, schema=SCHEMA, out_schema=None, unique="unique", duplicate="duplicate"):
    """file -> unique row -> out.csv (unique rows) and dup.csv (duplicate rows).

    ``unique`` and ``duplicate`` are the flow types; None leaves that output unwired.
    """
    component = {"id": "it", "type": "UniqueRow", "config": config,
                 "schema": {"input": columns(schema), "output": columns(out_schema or schema)},
                 "inputs": ["row1"], "outputs": []}
    components, flows = [reader(schema), component], [flow("row1", "in", "it")]
    if unique:
        component["outputs"].append("row2")
        components.append(writer(out_schema or schema))
        flows.append(flow("row2", "it", "out", unique))
    if duplicate:
        component["outputs"].append("row3")
        components.append(writer(schema, component_id="dup", path="dup.csv", inputs=("row3",)))
        flows.append(flow("row3", "it", "dup", duplicate))
    return job(components, flows)


def same(tmp_path, config, data=ROWS, **kwargs):
    """Both engines finish the job and write the same files."""
    run = assert_matches_v1(dedupe(config, **kwargs), {"in.csv": data}, tmp_path)
    assert run.succeeded, run.error
    return run


def v2(tmp_path, made, data=ROWS):
    """Run a job on v2 only, inside tmp_path."""
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def refused(config, **kwargs):
    with pytest.raises(JobRefusedError) as caught:
        load_job(dedupe(config, **kwargs))
    return caught.value.report.format()


# ------------------------------------------------------------------
# Which rows are unique, and the order they leave in
# ------------------------------------------------------------------

def test_first_row_of_each_key_is_unique_and_the_rest_are_duplicates(tmp_path):
    run = same(tmp_path, {"key_columns": BY_NAME})
    assert run.files["out.csv"] == HEADER + b"1;a;1.5\n2;b;2.5\n3;A;3.5\n5;c;5.5\n6;B;6.5\n"
    assert run.files["dup.csv"] == HEADER + b"4;a;4.5\n7;a;7.5\n"


def test_key_can_ignore_case(tmp_path):
    run = same(tmp_path, {"key_columns": ANY_CASE})
    assert run.files["out.csv"] == HEADER + b"1;a;1.5\n2;b;2.5\n5;c;5.5\n"
    assert run.files["dup.csv"] == HEADER + b"3;A;3.5\n4;a;4.5\n6;B;6.5\n7;a;7.5\n"


def test_last_row_of_each_key_can_be_the_unique_one(tmp_path):
    run = same(tmp_path, {"key_columns": ANY_CASE, "keep": "last"})
    assert run.files["out.csv"] == HEADER + b"5;c;5.5\n6;B;6.5\n7;a;7.5\n"
    assert run.files["dup.csv"] == HEADER + b"1;a;1.5\n2;b;2.5\n3;A;3.5\n4;a;4.5\n"


def test_keep_false_makes_every_row_of_a_repeated_key_a_duplicate(tmp_path):
    run = same(tmp_path, {"key_columns": ANY_CASE, "keep": False})
    assert run.files["out.csv"] == HEADER + b"5;c;5.5\n"


@pytest.mark.parametrize("keep", ["first", "last", False])
@pytest.mark.parametrize("keys", [BY_NAME, ANY_CASE])
def test_only_the_first_duplicate_of_each_key_can_be_asked_for(tmp_path, keep, keys):
    same(tmp_path, {"key_columns": keys, "keep": keep, "only_once_each_duplicated_key": True})


def test_only_once_each_duplicated_key_names_the_first_duplicate(tmp_path):
    run = same(tmp_path, {"key_columns": ANY_CASE, "only_once_each_duplicated_key": True})
    assert run.files["dup.csv"] == HEADER + b"3;A;3.5\n6;B;6.5\n"


def test_rows_are_made_unique_where_the_component_stands_in_the_job(tmp_path):
    made = dedupe({"key_columns": ANY_CASE})
    declared = {"input": columns(SCHEMA), "output": columns(SCHEMA)}
    kept = {"id": "keep", "type": "FilterRows", "schema": declared, "inputs": ["row1"], "outputs": ["row0"],
            "config": {"conditions": [{"column": "amt", "operator": ">", "value": "2"}]}}
    ordered = {"id": "order", "type": "SortRow", "schema": declared, "inputs": ["row2"], "outputs": ["row4"],
               "config": {"criteria": [{"column": "id", "sort_type": "num", "order": "desc"}]}}
    made["components"][1]["inputs"] = ["row0"]
    made["components"][2]["inputs"] = ["row4"]
    made["components"] += [kept, ordered]
    made["flows"] = [flow("row1", "in", "keep"), flow("row0", "keep", "it", "filter"),
                     flow("row2", "it", "order", "unique"), flow("row4", "order", "out"),
                     flow("row3", "it", "dup", "duplicate")]
    run = assert_matches_v1(made, {"in.csv": ROWS}, tmp_path)
    assert run.files["out.csv"] == HEADER + b"5;c;5.5\n3;A;3.5\n2;b;2.5\n"
    assert run.files["dup.csv"] == HEADER + b"4;a;4.5\n6;B;6.5\n7;a;7.5\n"


# ------------------------------------------------------------------
# Key columns
# ------------------------------------------------------------------

def test_key_columns_can_be_plain_names(tmp_path):
    run = same(tmp_path, {"key_columns": ["name"]})
    assert run.files["dup.csv"] == HEADER + b"4;a;4.5\n7;a;7.5\n"


def test_key_column_without_a_case_flag_takes_the_component_wide_one(tmp_path):
    for folder, keys in (("name", ["name"]), ("object", [{"column": "name"}])):
        run = same(tmp_path / folder, {"key_columns": keys, "case_sensitive": False})
        assert run.files["dup.csv"] == HEADER + b"3;A;3.5\n4;a;4.5\n6;B;6.5\n7;a;7.5\n"


def test_key_columns_own_case_flag_wins_over_the_component_wide_one(tmp_path):
    run = same(tmp_path, {"key_columns": BY_NAME, "case_sensitive": False})
    assert run.files["dup.csv"] == HEADER + b"4;a;4.5\n7;a;7.5\n"


def test_without_key_columns_the_whole_row_is_the_key(tmp_path):
    run = same(tmp_path, {}, data=ROWS + b"1;a;1.5\n3;A;3.5\n8;a;1.5\n")
    assert run.files["dup.csv"] == HEADER + b"1;a;1.5\n3;A;3.5\n"
    run = same(tmp_path / "any_case", {"case_sensitive": False}, data=b"1;a;1.5\n1;A;1.5\n1;a;2.5\n")
    assert run.files["dup.csv"] == HEADER + b"1;A;1.5\n"


def test_several_key_columns_each_with_its_own_case_flag(tmp_path):
    data = b"1;a;1.5\n1;A;9\n2;a;1.5\n1;a;7\n2;A;0\n"
    keys = [{"column": "id", "case_sensitive": True}, {"column": "name", "case_sensitive": False}]
    run = same(tmp_path, {"key_columns": keys}, data=data)
    assert run.files["dup.csv"] == HEADER + b"1;A;9.0\n1;a;7.0\n2;A;0.0\n"
    run = same(tmp_path / "exact", {"key_columns": ["id", "name"]}, data=data)
    assert run.files["dup.csv"] == HEADER + b"1;a;7.0\n"


def test_ignoring_case_changes_nothing_for_a_column_that_is_not_text(tmp_path):
    keys = [{"column": "id", "case_sensitive": False}]
    run = same(tmp_path, {"key_columns": keys}, data=b"1;a;1.5\n1;b;2.5\n2;c;3.5\n")
    assert run.files["dup.csv"] == HEADER + b"1;b;2.5\n"


def test_a_key_column_named_twice_counts_once(tmp_path):
    assert same(tmp_path, {"key_columns": ["name", "name"]}).files["dup.csv"] == HEADER + b"4;a;4.5\n7;a;7.5\n"


EVERY_TYPE = "id:int, k:int, f:float, m:Decimal, d:datetime@%Y-%m-%d, b:bool, s:str"
EVERY_TYPE_ROWS = (
    b"1;;;;;;\n"
    b"2;;;;;;\n"
    b"3;7;1.5;1.50;2024-01-01;true;a\n"
    b"4;7;1.5;1.5;2024-01-01;true;A\n"
    b"5;7;1.50;1.500;2024-01-01;false; a\n"
    b"6;0;0.0;0;2024-01-02;false;\n"
    b"7;0;-0.0;0.0;2024-01-02;false;\n"
    b"8;;;;;;\n"
)


@pytest.mark.parametrize("key", ["k", "f", "m", "d", "b", "s"])
@pytest.mark.parametrize("keep", ["first", "last", False])
def test_missing_values_are_one_key_and_equal_numbers_are_one_key(tmp_path, key, keep):
    same(tmp_path, {"key_columns": [key], "keep": keep}, data=EVERY_TYPE_ROWS, schema=EVERY_TYPE)


def test_missing_values_as_keys_look_like_this(tmp_path):
    run = same(tmp_path, {"key_columns": ["k"]}, data=EVERY_TYPE_ROWS, schema=EVERY_TYPE)
    assert [line.split(b";")[0] for line in run.files["out.csv"].splitlines()[1:]] == [b"1", b"3", b"6"]


@pytest.mark.parametrize("once", [False, True])
def test_missing_values_in_a_key_of_several_columns(tmp_path, once):
    config = {"key_columns": ["k", "s"], "only_once_each_duplicated_key": once}
    run = same(tmp_path, config, data=b"1;;x\n2;;x\n3;;y\n4;5;\n5;5;\n6;;\n7;;\n8;;x\n", schema="id:int, k:int, s:str")
    assert run.files["dup.csv"] == b"id;k;s\n2;;x\n5;5;\n7;;\n" + (b"" if once else b"8;;x\n")


def test_a_float_that_is_not_a_number_is_a_missing_value_as_a_key(tmp_path):
    # No file holds one: a file input reads the text NaN as a missing value. Rows written in the config can.
    registry = Registry()
    for cls in (stand_ins.Rows, stand_ins.Save, REGISTRY.get("unique_row")):
        registry.register(cls)
    made = stand_ins.job(
        [("in", "rows", {"data": {"id": [1, 2, 3, 4], "x": [float("nan"), None, 1.5, float("nan")]}}),
         ("it", "unique_row", {"key_columns": ["x"]}), ("out", "save", {"path": str(tmp_path / "out.csv")})],
        [("row1", "in", "it", "flow"), ("row2", "it", "out", "unique")],
    )
    assert run_job(made, registry=registry).status == "success"
    assert stand_ins.lines(tmp_path / "out.csv") == ["id,x", "1,NaN", "3,1.5"]


# ------------------------------------------------------------------
# Outputs
# ------------------------------------------------------------------

def test_no_duplicates_writes_an_empty_duplicate_file(tmp_path):
    run = same(tmp_path, {"key_columns": ["id"]})
    assert run.files["dup.csv"] == HEADER
    assert run.files["out.csv"] == HEADER + ROWS


def test_empty_input_writes_two_empty_files(tmp_path):
    run = same(tmp_path, {"key_columns": BY_NAME}, data=b"")
    assert run.files == {"out.csv": HEADER, "dup.csv": HEADER}


@pytest.mark.parametrize(
    "unique, duplicate", [("unique", None), ("flow", None), (None, "duplicate"), ("flow", "reject")]
)
def test_flow_types_and_outputs_left_unwired(tmp_path, unique, duplicate):
    run = same(tmp_path, {"key_columns": BY_NAME}, unique=unique, duplicate=duplicate)
    assert sorted(run.files) == [name for name, wired in (("dup.csv", duplicate), ("out.csv", unique)) if wired]


def test_unique_rows_also_leave_by_a_flow_typed_main(tmp_path):
    # v1 does not route a flow typed "main" and stalls.
    result = v2(tmp_path, dedupe({"key_columns": BY_NAME}, unique="main", duplicate=None))
    assert result.status == "success"
    assert (tmp_path / "out.csv").read_bytes() == HEADER + b"1;a;1.5\n2;b;2.5\n3;A;3.5\n5;c;5.5\n6;B;6.5\n"


@pytest.mark.parametrize("once", [False, True])
def test_duplicates_can_be_switched_off(tmp_path, once):
    config = {"key_columns": BY_NAME, "output_duplicates": False, "only_once_each_duplicated_key": once}
    assert same(tmp_path, config).files["dup.csv"] == HEADER


def test_declared_output_columns_decide_the_order_of_the_unique_rows_only(tmp_path):
    run = same(tmp_path, {"key_columns": BY_NAME}, out_schema="amt:float, id:int")
    assert run.files["out.csv"].splitlines()[:2] == [b"amt;id;name", b"1.5;1;a"]
    assert run.files["dup.csv"] == HEADER + b"4;a;4.5\n7;a;7.5\n"


def test_declared_reject_columns_decide_the_order_of_the_duplicates(tmp_path):
    made = dedupe({"key_columns": BY_NAME})
    made["components"][1]["schema"]["reject"] = columns("amt:float, id:int")
    run = assert_matches_v1(made, {"in.csv": ROWS}, tmp_path)
    assert run.files["dup.csv"] == b"amt;id;name\n4.5;4;a\n7.5;7;a\n"


def test_missing_value_in_a_column_that_allows_none_fails_the_job(tmp_path):
    made = dedupe({"key_columns": BY_NAME}, out_schema="id:int, name:str, amt:float!")
    run = assert_matches_v1(made, {"in.csv": b"1;a;1.5\n2;b;\n"}, tmp_path)
    assert not run.succeeded
    assert "Column 'amt' has NULL values but is not nullable" in run.error


# ------------------------------------------------------------------
# Counts other parts of the job can read
# ------------------------------------------------------------------

def counting(config, condition):
    """The dedupe job plus a subjob that copies flag.csv to yes.csv when the condition holds."""
    made = dedupe(config)
    made["components"] += [reader("a:str", component_id="in2", path="flag.csv", outputs=("row9",)),
                           writer("a:str", component_id="yes", path="yes.csv", inputs=("row9",))]
    made["flows"].append(flow("row9", "in2", "yes"))
    made["triggers"] = [{"type": "RunIf", "from": "it", "to": "in2", "condition": condition}]
    return made


def count(name):
    return f'((Integer)globalMap.get("it_{name}"))'


FILES = {"in.csv": ROWS, "flag.csv": b"x\n"}


@pytest.mark.parametrize(
    "config, uniques, duplicates",
    [
        ({"key_columns": BY_NAME}, 5, 2),
        ({"key_columns": ANY_CASE}, 3, 4),
        ({"key_columns": ANY_CASE, "keep": False}, 1, 6),
        ({"key_columns": ANY_CASE, "only_once_each_duplicated_key": True}, 3, 4),
        ({"key_columns": ANY_CASE, "output_duplicates": False}, 3, 4),
    ],
)
def test_numbers_of_unique_and_duplicate_rows_are_put_in_the_global_map(tmp_path, config, uniques, duplicates):
    right = f"{count('NB_UNIQUES')} == {uniques} && {count('NB_DUPLICATES')} == {duplicates}"
    assert assert_matches_v1(counting(config, right), FILES, tmp_path).files["yes.csv"] == b"a\nx\n"
    wrong = f"{count('NB_UNIQUES')} != {uniques} || {count('NB_DUPLICATES')} != {duplicates}"
    assert "yes.csv" not in assert_matches_v1(counting(config, wrong), FILES, tmp_path / "not").files


def test_engine_row_counts_follow_the_two_outputs(tmp_path):
    condition = f"{count('NB_LINE')} == 7 && {count('NB_LINE_OK')} == 5 && {count('NB_LINE_REJECT')} == 2"
    run = assert_matches_v1(counting({"key_columns": BY_NAME}, condition), FILES, tmp_path)
    assert run.files["yes.csv"] == b"a\nx\n"


def test_counts_of_an_empty_input_are_zero(tmp_path):
    (tmp_path / "flag.csv").write_bytes(b"x\n")
    condition = f"{count('NB_UNIQUES')} == 0 && {count('NB_DUPLICATES')} == 0"
    result = v2(tmp_path, counting({"key_columns": BY_NAME}, condition), data=b"")
    assert result.global_map["it_NB_UNIQUES"] == 0 and result.global_map["it_NB_DUPLICATES"] == 0
    assert (tmp_path / "yes.csv").exists()


def test_unique_and_duplicate_counts_are_taken_only_when_the_job_reads_them(tmp_path):
    result = v2(tmp_path, dedupe({"key_columns": BY_NAME}))
    assert result.status == "success"
    assert "it_NB_UNIQUES" not in result.global_map and "it_NB_DUPLICATES" not in result.global_map


@pytest.mark.parametrize(
    "config, rejected",
    [
        ({"key_columns": BY_NAME}, 2),
        ({"key_columns": BY_NAME, "only_once_each_duplicated_key": True}, 2),
        ({"key_columns": BY_NAME, "output_duplicates": False}, 2),
        ({"key_columns": BY_NAME, "is_reject_duplicate": False}, 0),
    ],
)
def test_rejected_row_count_is_every_duplicate_as_in_v1(tmp_path, config, rejected):
    condition = f"{count('NB_LINE')} == 7 && {count('NB_LINE_OK')} == 5 && {count('NB_LINE_REJECT')} == {rejected}"
    run = assert_matches_v1(counting(config, condition), FILES, tmp_path)
    assert run.succeeded and run.files["yes.csv"] == b"a\nx\n"


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "config, said",
    [
        ({"key_columns": ["nope"]}, "there is no column 'nope'"),
        ({"key_columns": ["name", {"column": "nope", "case_sensitive": False}]}, "there is no column 'nope'"),
        ({"key_columns": [{"column": ""}]}, "key_columns[0].column"),
        ({"key_columns": "name"}, "key_columns"),
        ({"key_columns": [{"column": "name", "bogus": 1}]}, "key_columns[0].bogus"),
        ({"keep": "bogus"}, "keep"),
        ({"keep": "none"}, "keep"),
        ({"keep": True}, "keep"),
        ({"bogus": 1}, "bogus"),
    ],
)
def test_refused_config(config, said):
    assert said in refused(config)


def test_keys_v1_ignores_are_accepted():
    load_job(dedupe({
        "key_columns": BY_NAME, "keep": "first", "case_sensitive": True, "only_once_each_duplicated_key": False,
        "output_duplicates": True, "is_reject_duplicate": True, "is_virtual_component": True, "buffer_size": "B",
        "temp_directory": "C:/tmp", "change_hash_and_equals_for_bigdecimal": True, "tstatcatcher_stats": False,
        "label": "Deduplicate_Email",
    }))


def test_the_converters_sample_loads():
    sample = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tUniqRow_0.1.json"
    converted = next(c for c in json.loads(sample.read_text())["components"] if c["type"] == "UniqueRow")
    made = dedupe(converted["config"])
    made["components"][0]["schema"]["output"] = converted["schema"]["input"]
    made["components"][1]["schema"] = converted["schema"]
    load_job(made)
