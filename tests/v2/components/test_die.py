"""Die: the job is stopped with a message. Against v1 where a job stops or goes on in both."""
import logging
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1
from tests.v2.components.kit import columns, flow, job, reader, writer

COPY = [reader("id:int", component_id="in"), writer("id:int", inputs=("row1",))]


def die(kind="Die", inputs=(), **config):
    return {"id": "stop", "type": kind, "config": config, "inputs": list(inputs), "outputs": [],
            "schema": {"input": columns("id:int") if inputs else [], "output": []}}


def after(trigger, **config):
    """file -> file, then a die the trigger sets off."""
    made = job([*COPY, die(**config)], [flow("row1", "in", "out")])
    made["triggers"] = [{"from": "in", "to": "stop", **trigger}]
    return made


def v2(tmp_path, made, data=b"1\n2\n"):
    (tmp_path / "in.csv").write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def test_job_is_stopped_with_the_message(tmp_path):
    made = after({"type": "OnSubjobOk"}, message="enough")
    assert_matches_v1(made, {"in.csv": b"1\n"}, tmp_path)   # neither engine finishes
    (tmp_path / "x").mkdir()
    result = v2(tmp_path / "x", made)
    assert result.status == "failed" and result.failed_component == "stop"
    assert result.error == "Job terminated by tDie: enough (exit code: 1)"
    assert (tmp_path / "x" / "out.csv").exists()


def test_die_a_trigger_does_not_set_off_stops_nothing(tmp_path):
    made = after({"type": "RunIf", "condition": '((Integer)globalMap.get("in_NB_LINE")) > 5'}, message="enough")
    run = assert_matches_v1(made, {"in.csv": b"1\n"}, tmp_path)
    assert run.succeeded and run.files["out.csv"] == b"id\n1\n"


def test_die_set_off_when_a_subjob_fails(tmp_path):
    made = after({"type": "OnSubjobError"}, message="the copy failed")
    made["components"][0]["config"]["die_on_error"] = True
    result = v2(tmp_path, made, b"1\nx\n")
    assert result.status == "failed" and result.failures["stop"] == "Job terminated by tDie: the copy failed (exit code: 1)"


def test_what_it_leaves_in_globalmap_under_v1s_names_and_talends(tmp_path):
    result = v2(tmp_path, after({"type": "OnSubjobOk"}, message="enough", code="7", priority="3", exit_code=9))
    held = {key: value for key, value in result.global_map.items() if key.startswith("stop_") or key.startswith("JOB_")}
    assert held == {
        "stop_MESSAGE": "enough", "stop_CODE": 7, "stop_PRIORITY": 3, "stop_EXIT_CODE": 9,
        "stop_DIE_MESSAGE": "enough", "stop_DIE_MESSAGES": "enough", "stop_DIE_CODE": 7, "stop_DIE_PRIORITY": 3,
        "JOB_ERROR_MESSAGE": "enough", "JOB_EXIT_CODE": 9,
    }
    assert result.error == "Job terminated by tDie: enough (exit code: 9)"


def test_defaults(tmp_path):
    result = v2(tmp_path, after({"type": "OnSubjobOk"}))
    assert result.error == "Job terminated by tDie: the end is near (exit code: 1)"
    assert result.global_map["stop_CODE"] == 4 and result.global_map["stop_PRIORITY"] == 5


@pytest.mark.parametrize("priority, level", [(1, "DEBUG"), (2, "DEBUG"), (3, "INFO"), (4, "WARNING"), (5, "ERROR"), (6, "CRITICAL")])
def test_message_is_logged_with_its_code_at_the_level_of_its_priority(tmp_path, caplog, priority, level):
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        v2(tmp_path, after({"type": "OnSubjobOk"}, message="enough", code=7, priority=priority))
    said = [(record.levelname, record.getMessage()) for record in caplog.records if "Code 7" in record.getMessage()]
    assert said == [(level, "[stop] Code 7: enough")]


def test_entry_of_globalmap_and_a_context_value_in_the_message(tmp_path):
    made = after({"type": "OnSubjobOk"},
                 message='read ((Integer)globalMap.get("in_NB_LINE")) of ${context.what}, ((String)globalMap.get("nope")) more')
    made["context"] = {"Default": {"what": {"value": "orders", "type": "str"}}}
    result = v2(tmp_path, made)
    assert result.global_map["stop_MESSAGE"] == "read 2 of orders, 0 more"


# ------------------------------------------------------------------
# A die a flow leads to
# ------------------------------------------------------------------

def to_die(**config):
    """file -> filter; the rows it turns away -> die."""
    step = {"id": "it", "type": "FilterRows", "inputs": ["row1"], "outputs": ["row2", "bad"],
            "config": {"conditions": [{"column": "id", "function": "", "operator": ">", "value": "0"}]},
            "schema": {"input": columns("id:int"), "output": columns("id:int")}}
    made = job([reader("id:int", component_id="in"), step, writer("id:int"), die(inputs=("bad",), **config)],
               [flow("row1", "in", "it"), flow("row2", "it", "out"), flow("bad", "it", "stop", kind="reject")])
    return made


def test_die_a_flow_leads_to_stops_the_job_when_a_row_arrives_and_names_it(tmp_path):
    result = v2(tmp_path, to_die(message="a row was turned away"), b"1\n-2\n3\n-4\n")
    assert result.status == "failed" and result.failed_component == "stop"
    assert result.error == ("Job terminated by tDie: a row was turned away (exit code: 1) "
                            "(the first of 2 rows that came to it); the row is line 2 of in.csv")
    assert not (tmp_path / "out.csv").exists()
    assert result.global_map["stop_DIE_MESSAGE"] == "a row was turned away"


def test_die_a_flow_leads_to_stops_nothing_when_no_row_arrives_as_in_talend(tmp_path, caplog):
    # v1 stops the job here as well.
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        result = v2(tmp_path, to_die(message="a row was turned away"), b"1\n3\n")
    assert result.status == "success" and (tmp_path / "out.csv").read_bytes() == b"id\n1\n3\n"
    assert "stop_MESSAGE" not in result.global_map
    assert not [record for record in caplog.records if "Code 4" in record.getMessage()]


def test_job_with_a_die_is_checked_without_dying():
    load_job(after({"type": "OnSubjobOk"}, message="enough"))
    load_job(to_die())


@pytest.mark.parametrize("config, key", [
    ({"priority": 7}, "priority"), ({"priority": "high"}, "priority"), ({"code": "x"}, "code"), ({"exit_code": "x"}, "exit_code"),
    ({"exit_jvm": True}, "exit_jvm"), ({"nope": 1}, "nope"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(after({"type": "OnSubjobOk"}, **config))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_number_that_is_none_is_said_plainly():
    with pytest.raises(JobRefusedError) as refused:
        load_job(after({"type": "OnSubjobOk"}, code="x"))
    assert [refusal.reason for refusal in refused.value.report] == ["'x' is no code: give a whole number"]
    with pytest.raises(JobRefusedError) as refused:
        load_job(after({"type": "OnSubjobOk"}, exit_code=[1]))
    assert [refusal.reason for refusal in refused.value.report] == ["[1] is no exit code: give a whole number"]


def test_flow_out_of_it_is_refused():
    made = job([die(), writer("id:int", inputs=("row1",))], [flow("row1", "stop", "out")])
    made["components"][0]["outputs"] = ["row1"]
    with pytest.raises(JobRefusedError):
        load_job(made)


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("die", "Die", "tDie")):
        (tmp_path / str(at)).mkdir()
        made = after({"type": "OnSubjobOk"}, message="enough")
        made["components"][2]["type"] = kind
        assert v2(tmp_path / str(at), made).error.startswith("Job terminated by tDie: enough")
