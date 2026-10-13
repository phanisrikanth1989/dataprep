"""Set global var, against v1: what a later subjob reads from globalMap."""
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1
from tests.v2.components.kit import columns, flow, job, reader, writer

ROWS = "id:int, name:str, amt:float"
DATA = b"1;ann;1.5\n2;bob;2.5\n"


def setter(kind="SetGlobalVar", inputs=(), outputs=(), **config):
    return {"id": "set", "type": kind, "config": config, "inputs": list(inputs), "outputs": list(outputs),
            "schema": {"input": columns(ROWS) if inputs else [], "output": columns(ROWS) if outputs else []}}


def variables(**held):
    return [{"key": key, "value": value} for key, value in held.items()]


def reading(*keys):
    """A later subjob that writes the entries of globalMap it is asked for, one a column, to g.csv."""
    source = {"id": "gen", "type": "FixedFlowInputComponent", "inputs": [], "outputs": ["g1"],
              "config": {"nb_rows": 1, "values_config": [{"schema_column": key, "value": f'globalMap.get("{key}")'} for key in keys]},
              "schema": {"input": [], "output": [{"name": key, "type": "str", "nullable": True} for key in keys]}}
    return [source, writer(", ".join(f"{key}:str" for key in keys), component_id="gout", path="g.csv", inputs=("g1",))]


def alone(*keys, **config):
    made = job([setter(**config), *reading(*keys)], [flow("g1", "gen", "gout")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "set", "to": "gen"}]
    return made


def in_flow(*keys, **config):
    """file -> set -> file, then the reading subjob."""
    made = job([reader(ROWS), setter(inputs=("row1",), outputs=("row2",), **config), writer(ROWS), *reading(*keys)],
               [flow("row1", "in", "set"), flow("row2", "set", "out"), flow("g1", "gen", "gout")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "in", "to": "gen"}]
    return made


def v2(tmp_path, made, data=DATA):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def test_entries_are_there_for_a_later_subjob(tmp_path):
    run = assert_matches_v1(alone("who", "n", variables=variables(who="ann", n=5)), {}, tmp_path)
    assert run.files["g.csv"] == b"who;n\nann;5\n"


def test_entry_keeps_the_kind_of_value_it_was_given(tmp_path):
    result = v2(tmp_path, alone("who", variables=variables(who="ann", n=5, f=1.5, ok=True, none=None, text="007")))
    held = {key: result.global_map[key] for key in ("who", "n", "f", "ok", "none", "text")}
    assert held == {"who": "ann", "n": 5, "f": 1.5, "ok": True, "none": None, "text": "007"}


def test_context_value_in_a_value_and_a_trigger_that_reads_an_entry(tmp_path):
    made = alone("who", variables=variables(who="${context.name}", go="Y"))
    made["context"] = {"Default": {"name": {"value": "cy", "type": "str"}}}
    made["triggers"] = [{"type": "RunIf", "from": "set", "to": "gen", "condition": '((String)globalMap.get("go")) == "Y"'}]
    assert assert_matches_v1(made, {}, tmp_path).files["g.csv"] == b"who\ncy\n"
    made["triggers"][0]["condition"] = '((String)globalMap.get("go")) == "N"'
    assert "g.csv" not in assert_matches_v1(made, {}, tmp_path / "b").files


def test_later_entry_of_the_same_key_stays_and_no_variables_put_nothing(tmp_path):
    held = [{"key": "who", "value": "ann"}, {"key": "who", "value": "bob"}]
    assert assert_matches_v1(alone("who", variables=held), {}, tmp_path).files["g.csv"] == b"who\nbob\n"
    assert v2(tmp_path, alone("who", variables=[])).status == "success"


def test_v1s_other_spellings(tmp_path):
    made = alone("who", VARIABLES=[{"name": "who", "VALUE": "ann"}])
    assert assert_matches_v1(made, {}, tmp_path).files["g.csv"] == b"who\nann\n"


# ------------------------------------------------------------------
# With a flow leading to it
# ------------------------------------------------------------------

def test_rows_pass_through_and_a_column_of_the_last_row_stays(tmp_path):
    made = in_flow("last", "lit", variables=variables(last="row1.name", lit="x"))
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.files["out.csv"] == b"id;name;amt\n1;ann;1.5\n2;bob;2.5\n" and run.files["g.csv"] == b"last;lit\nbob;x\n"


def test_value_of_the_row_keeps_its_type(tmp_path):
    result = v2(tmp_path, in_flow("a", variables=variables(a="row1.id", b="row1.amt", c="row1.name")))
    assert (result.global_map["a"], result.global_map["b"], result.global_map["c"]) == (2, 2.5, "bob")
    assert isinstance(result.global_map["a"], int)


def test_text_with_a_dot_that_names_no_column_of_the_flow_is_the_text_itself(tmp_path):
    made = in_flow("f", "g", variables=variables(f="data.csv", g="row1.nope"))
    assert assert_matches_v1(made, {"in.csv": DATA}, tmp_path).files["g.csv"] == b"f;g\ndata.csv;row1.nope\n"


def test_word_before_the_dot_has_to_be_the_flows_name(tmp_path):
    # v1 takes any word before the dot: `other.name` is the column name there too.
    result = v2(tmp_path, in_flow("a", variables=variables(a="other.name")))
    assert result.global_map["a"] == "other.name"


def test_nothing_is_put_when_no_row_arrives_as_in_talend(tmp_path):
    # v1 puts the values as they are written, the text row1.name among them.
    result = v2(tmp_path, in_flow("last", variables=variables(last="row1.name", lit="x")), b"")
    assert result.status == "success" and "last" not in result.global_map and "lit" not in result.global_map


def test_flow_may_end_at_it(tmp_path):
    made = job([reader(ROWS), setter(inputs=("row1",), variables=variables(last="row1.id"))], [flow("row1", "in", "set")])
    assert v2(tmp_path, made).global_map["last"] == 2


def test_component_of_the_same_subjob_that_reads_an_entry_fails_the_job(tmp_path):
    made = in_flow("last", variables=variables(last="row1.name"))
    step = {"id": "it", "type": "FilterRows", "inputs": ["row2"], "outputs": ["row3"],
            "config": {"conditions": [{"column": "name", "function": "", "operator": "==", "value": '((String)globalMap.get("last"))'}]},
            "schema": {"input": columns(ROWS), "output": columns(ROWS)}}
    made["components"].insert(2, step)
    made["components"][3]["inputs"] = ["row3"]
    made["flows"][1:2] = [flow("row2", "set", "it"), flow("row3", "it", "out")]
    result = v2(tmp_path, made)
    assert result.status == "failed" and result.failed_component == "set"
    assert result.error == ("'it' reads the globalMap entry 'last' in the same subjob: v2 puts it when the subjob is done, "
                            "not row by row as v1 does; read it in a subjob that follows")
    assert not (tmp_path / "out.csv").exists()


def test_value_that_names_its_own_key_is_no_reader_of_it(tmp_path):
    result = v2(tmp_path, in_flow("who", variables=variables(who='the key "who"')))
    assert result.status == "success" and result.global_map["who"] == 'the key "who"'


def test_rows_are_counted_as_v1_counts_them(tmp_path):
    made = dict(in_flow("lit", variables=variables(lit="x")), run={"row_counts": True})
    result = v2(tmp_path, made)
    assert result.counts["set"] == {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}


def test_job_is_checked_without_anything_being_put():
    load_job(alone("who", variables=variables(who="ann")))
    load_job(in_flow("who", variables=variables(who="row1.name")))


@pytest.mark.parametrize("config, key", [
    ({}, "variables"), ({"variables": "x"}, "variables"), ({"variables": [{"value": "x"}]}, "variables[0].key"),
    ({"variables": [{"key": "", "value": "x"}]}, "variables[0].key"), ({"variables": [], "nope": 1}, "nope"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(alone("who", **config))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("set_global_var", "SetGlobalVar", "tSetGlobalVar")):
        (tmp_path / str(at)).mkdir()
        made = alone("who", variables=variables(who="ann"))
        made["components"][0]["type"] = kind
        assert v2(tmp_path / str(at), made).global_map["who"] == "ann"


# ------------------------------------------------------------------
# What an independent review found (ticket 84)
# ------------------------------------------------------------------

def test_trigger_that_leaves_a_component_before_it_does_not_see_its_entries_yet_as_in_v1(tmp_path):
    def stage(name):
        return ([reader("n:str", component_id=f"{name}_in", path=f"{name}.csv", outputs=(f"{name}_row",)),
                 writer("n:str", component_id=f"{name}_out", path="order.csv", inputs=(f"{name}_row",),
                        include_header=False, append=True)],
                [flow(f"{name}_row", f"{name}_in", f"{name}_out")])
    made = job([reader(ROWS), setter(inputs=("row1",), outputs=("row2",), variables=variables(go="Y")), writer(ROWS)],
               [flow("row1", "in", "set"), flow("row2", "set", "out")])
    for name in ("s", "t"):
        parts, flows = stage(name)
        made["components"] += parts
        made["flows"] += flows
    made["triggers"] = [
        {"type": "RunIf", "from": "in", "to": "t_in", "condition": '((String)globalMap.get("go")) == "Y"', "order": 1},
        {"type": "OnSubjobOk", "from": "in", "to": "s_in", "order": 2},
    ]
    run = assert_matches_v1(made, {"in.csv": DATA, "s.csv": b"s\n", "t.csv": b"t\n"}, tmp_path)
    assert run.files["order.csv"] == b"s\nt\n"


def with_step(config, **more):
    made = in_flow("last", variables=variables(last="row1.name", bob="x"))
    step = {"id": "it", "type": "FilterRows", "inputs": ["row2"], "outputs": ["row3"], "config": {**config, **more},
            "schema": {"input": columns(ROWS), "output": columns(ROWS)}}
    made["components"].insert(2, step)
    made["components"][3]["inputs"] = ["row3"]
    made["flows"][1:2] = [flow("row2", "set", "it"), flow("row3", "it", "out")]
    return made


@pytest.mark.parametrize("config", [
    {"conditions": [{"column": "name", "function": "", "operator": "==", "value": "bob"}], "label": 'uses "last" and "bob"'},
    {"conditions": [{"column": "name", "function": "", "operator": "==", "value": '"bob"'}]},
])
def test_text_that_only_holds_a_key_as_a_word_is_no_reader_of_it(tmp_path, config):
    result = v2(tmp_path, with_step(config))
    assert result.status == "success", result.error


@pytest.mark.parametrize("written", ['globalMap.get("last")', "globalMap.get('last')", 'globalMap.get( "last" )',
                                     '((String)globalMap.get("last"))', 'globalMap["last"]'])
def test_every_way_of_reading_an_entry_in_the_same_subjob_fails_the_job(tmp_path, written):
    result = v2(tmp_path, with_step({"conditions": [{"column": "name", "function": "", "operator": "==", "value": written}]}))
    assert result.status == "failed" and result.failed_component == "set" and "'last'" in result.error


def test_blanks_around_a_column_of_the_row_and_text_that_only_starts_like_one(tmp_path):
    result = v2(tmp_path, in_flow("a", variables=variables(a="  row1.name  ", b="row1.name + 1", c=7)))
    assert result.global_map["a"] == "bob" and result.global_map["b"] == "row1.name + 1" and result.global_map["c"] == 7


def test_one_that_is_to_hand_rows_on_and_gets_none_refuses_the_job():
    made = job([setter(outputs=("row2",), variables=variables(a="x")), writer(ROWS)], [flow("row2", "set", "out")])
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    assert [refusal.key for refusal in refused.value.report] == ["outputs"]


@pytest.mark.parametrize("held, key", [(None, "variables"), ([{"key": None, "value": 1}], "variables[0].key")])
def test_nothing_where_the_entries_or_a_key_should_be_refuses_the_job(held, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(alone("who", variables=held))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_reader_of_an_earlier_subjob_is_no_reader_of_this_one(tmp_path):
    # An earlier subjob reads the entry (and finds none); the subjob that puts it is not failed for that.
    made = in_flow("last", variables=variables(last="row1.name"))
    made["triggers"] = [{"type": "OnSubjobOk", "from": "gen", "to": "in"}]
    result = v2(tmp_path, made)
    assert result.status == "success", result.error
