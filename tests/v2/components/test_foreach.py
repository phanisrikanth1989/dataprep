"""Foreach: a loop over values written in the job config."""
import logging
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, reader, writer

VALUE = '((String)globalMap.get("each_CURRENT_VALUE"))'
FILES = {"a.csv": b"1\n2\n", "b.csv": b"3\n", "c.csv": b""}


def foreach(kind="Foreach", **config):
    return {"id": "each", "type": kind, "config": config, "inputs": [], "outputs": ["it"],
            "schema": {"input": [], "output": []}}


def looped(values, kind="Foreach", **config):
    """foreach -iterate-> a reader of the file the value names -> out.csv, which every pass adds to."""
    body = [reader("id:int", path="{{java}}" + VALUE), writer("id:int", inputs=("row1",), append=True, include_header=False)]
    made = job([foreach(kind, values=list(values), **config), *body], [flow("row1", "in", "out")])
    made["flows"].append({"name": "it", "from": "each", "to": "in", "type": "iterate"})
    return made


def ran(tmp_path, made, files=FILES):
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    return result, (tmp_path / "out.csv").read_bytes() if (tmp_path / "out.csv").exists() else None


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


def test_body_runs_for_each_value_in_the_order_they_are_written(tmp_path):
    result, out = ran(tmp_path, looped(["b.csv", "a.csv", "c.csv"]))
    assert result.status == "success", result.error
    assert out == b"3\n1\n2\n"
    assert result.rows == {"out": 3}
    assert result.summary()["loops"] == {"each": {"items": 3, "passes": 3}}


def test_what_it_leaves_in_globalmap(tmp_path):
    result, _ = ran(tmp_path, dict(looped(["a.csv", "b.csv"]), run={"row_counts": True}))
    held = {key: value for key, value in result.global_map.items() if key.startswith("each_")}
    assert held == {"each_CURRENT_VALUE": "b.csv", "each_CURRENT_ITERATION": 2, "each_NB_LINE": 2, "each_NB_LINE_OK": 2,
                    "each_NB_LINE_REJECT": 0}
    assert result.counts["each"] == {"NB_LINE": 2, "NB_LINE_OK": 2, "NB_LINE_REJECT": 0}


def test_value_is_text_as_it_is_written_and_a_context_variable_is_put_in(tmp_path):
    made = looped(["${context.first}", "b.csv"])
    made["context"] = {"Default": {"first": {"value": "a.csv", "type": "str"}}}
    result, out = ran(tmp_path, made)
    assert result.status == "success" and out == b"1\n2\n3\n"


def test_value_that_looks_like_a_number_stays_the_text_it_is(tmp_path):
    result, _ = ran(tmp_path, job([foreach(values=["007", "1.50"])], []), {})
    assert result.global_map["each_NB_LINE"] == 2
    made = job([foreach(values=["007"]), {"id": "set", "type": "SetGlobalVar", "inputs": [], "outputs": [],
                                         "schema": {"input": [], "output": []},
                                         "config": {"variables": [{"key": "seen", "value": VALUE}]}}], [])
    made["flows"].append({"name": "it", "from": "each", "to": "set", "type": "iterate"})
    result, _ = ran(tmp_path, made, {})
    assert result.status == "success", result.error
    assert result.global_map["each_CURRENT_VALUE"] == "007"


def test_value_written_as_a_number_is_text_too_and_die_on_error_is_taken(tmp_path):
    made = job([foreach(values=[5, 1.5], die_on_error=True), {"id": "set", "type": "SetGlobalVar", "inputs": [], "outputs": [],
                                                              "schema": {"input": [], "output": []},
                                                              "config": {"variables": [{"key": "seen", "value": "x"}]}}], [])
    made["flows"].append({"name": "it", "from": "each", "to": "set", "type": "iterate"})
    result, _ = ran(tmp_path, made, {})
    assert result.status == "success", result.error
    assert result.global_map["each_CURRENT_VALUE"] == "1.5"


def test_no_value_no_pass(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    result, out = ran(tmp_path, looped([]))
    assert result.status == "success" and out is None
    assert result.global_map["each_NB_LINE"] == 0 and "each_CURRENT_VALUE" not in result.global_map
    assert "[each] no item: what it leads to is not run" in [record.getMessage() for record in caplog.records]


def test_pass_that_fails_stops_the_loop_and_names_the_value(tmp_path):
    result, out = ran(tmp_path, looped(["a.csv", "nope.csv", "b.csv"]))
    assert result.status == "failed" and out == b"1\n2\n"
    assert result.failures["each"].startswith("its loop stopped at item 2 of 3 (nope.csv): in failed: ")


def test_more_values_than_the_cap_fail_the_job_before_the_first_pass(tmp_path):
    result, out = ran(tmp_path, looped(["a.csv", "b.csv"], max_items=1))
    assert (result.status, out) == ("failed", None)
    assert result.error == "2 items, and a loop may have 1 by `max_items`: none is run"


def test_what_the_converter_writes_is_taken_and_alone_it_just_counts(tmp_path):
    made = job([foreach(kind="tForeach", values=["a", "b"], tstatcatcher_stats=False, label="")], [])
    result, _ = ran(tmp_path, made, {})
    assert result.status == "success" and result.global_map["each_NB_LINE"] == 2


@pytest.mark.parametrize("config, said", [
    ({"values": "a"}, "values: expected a list, got 'a'"), ({"values": [], "nope": 1}, "nope: unknown config key"),
    ({"values": [["a"]]}, "values: every value is text; [['a']] is not"),
])
def test_what_cannot_be_read_refuses_the_job(config, said):
    assert [f"{key}: {reason}" for key, reason in refusals(job([foreach(**config)], []))] == [said]


def test_flow_to_it_refuses_the_job():
    step = dict(foreach(values=["a"]), inputs=["row1"])
    made = job([reader("id:int"), step], [flow("row1", "in", "each")])
    assert refusals(made) == [("inputs", "takes no input, but 1 flow arrives")]


@pytest.mark.parametrize("kind", ["foreach", "Foreach", "tForeach"])
def test_every_name_of_it(tmp_path, kind):
    result, out = ran(tmp_path, looped(["a.csv"], kind=kind))
    assert result.status == "success" and out == b"1\n2\n"
