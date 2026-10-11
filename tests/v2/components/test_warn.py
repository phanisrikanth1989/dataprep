"""Warn: a message is logged and the job goes on. Against v1 for the files a job with one writes."""
import logging
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1
from tests.v2.components.kit import columns, flow, job, reader, writer

COPY = [reader("id:int", component_id="in"), writer("id:int", inputs=("row1",))]


def warn(kind="Warn", inputs=(), outputs=(), **config):
    return {"id": "say", "type": kind, "config": config, "inputs": list(inputs), "outputs": list(outputs),
            "schema": {"input": columns("id:int") if inputs else [], "output": columns("id:int") if outputs else []}}


def after(**config):
    """file -> file, then a warn."""
    made = job([*COPY, warn(**config)], [flow("row1", "in", "out")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "in", "to": "say"}]
    return made


def through(**config):
    """file -> warn -> file."""
    return job([reader("id:int", component_id="in"), warn(inputs=("row1",), outputs=("row2",), **config), writer("id:int")],
               [flow("row1", "in", "say"), flow("row2", "say", "out")])


def v2(tmp_path, made, caplog, data=b"1\n2\n"):
    (tmp_path / "in.csv").write_bytes(data)
    caplog.clear()
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        with caplog.at_level(logging.DEBUG, logger="src.v2"):
            result = run_job(made)
    finally:
        os.chdir(previous)
    said = [(record.levelname, record.getMessage()) for record in caplog.records if "] Code " in record.getMessage()]
    return result, said


def test_message_is_logged_and_the_job_goes_on(tmp_path, caplog):
    made = after(message="half way")
    made["components"] += [reader("id:int", component_id="in2", path="in.csv", outputs=("row9",)),
                           writer("id:int", component_id="out2", path="out2.csv", inputs=("row9",))]
    made["flows"].append(flow("row9", "in2", "out2"))
    made["triggers"].append({"type": "OnSubjobOk", "from": "say", "to": "in2"})
    run = assert_matches_v1(made, {"in.csv": b"1\n"}, tmp_path)
    assert run.succeeded and run.files["out2.csv"] == b"id\n1\n"
    (tmp_path / "x").mkdir()
    result, said = v2(tmp_path / "x", made, caplog)
    assert result.status == "success" and said == [("WARNING", "[say] Code 42: half way")]


def test_what_it_leaves_in_globalmap_under_v1s_names_and_talends(tmp_path, caplog):
    result, _ = v2(tmp_path, after(message="half way", code="7", priority="3"), caplog)
    held = {key: value for key, value in result.global_map.items() if key.startswith("say_") and "NB_LINE" not in key}
    assert held == {"say_MESSAGE": "half way", "say_CODE": 7, "say_PRIORITY": 3,
                    "say_WARN_MESSAGES": "half way", "say_WARN_CODE": 7, "say_WARN_PRIORITY": 3}


@pytest.mark.parametrize("priority, level", [(1, "DEBUG"), (3, "INFO"), (4, "WARNING"), (5, "ERROR"), (6, "CRITICAL")])
def test_level_is_that_of_the_priority(tmp_path, caplog, priority, level):
    _, said = v2(tmp_path, after(message="m", priority=priority), caplog)
    assert said == [(level, "[say] Code 42: m")]


def test_defaults_and_an_entry_of_globalmap_in_the_message(tmp_path, caplog):
    _, said = v2(tmp_path, after(), caplog)
    assert said == [("WARNING", "[say] Code 42: this is a warning")]
    (tmp_path / "b").mkdir()
    caplog.clear()
    _, said = v2(tmp_path / "b", after(message='read ((Integer)globalMap.get("in_NB_LINE")) rows'), caplog)
    assert said == [("WARNING", "[say] Code 42: read 2 rows")]


def test_rows_of_a_flow_pass_through_as_they_came(tmp_path, caplog):
    run = assert_matches_v1(through(message="rows went by"), {"in.csv": b"1\n2\n3\n"}, tmp_path)
    assert run.files["out.csv"] == b"id\n1\n2\n3\n"
    (tmp_path / "x").mkdir()
    result, said = v2(tmp_path / "x", through(message="rows went by"), caplog, b"1\n2\n3\n")
    assert said == [("WARNING", "[say] Code 42: rows went by")] and result.global_map["say_WARN_MESSAGES"] == "rows went by"


def test_warn_in_a_flow_says_nothing_when_no_row_arrives_as_in_talend(tmp_path, caplog):
    # v1 logs the message all the same.
    result, said = v2(tmp_path, through(message="rows went by"), caplog, b"")
    assert result.status == "success" and said == [] and "say_MESSAGE" not in result.global_map
    assert (tmp_path / "out.csv").read_bytes() == b"id\n"


def test_warn_a_flow_ends_at(tmp_path, caplog):
    made = job([reader("id:int", component_id="in"), warn(inputs=("row1",), message="seen")], [flow("row1", "in", "say")])
    result, said = v2(tmp_path, made, caplog)
    assert result.status == "success" and said == [("WARNING", "[say] Code 42: seen")]


def test_rows_are_counted_and_a_run_for_a_few_rows_sees_them_alone(tmp_path, caplog):
    made = dict(through(message="m"), run={"row_counts": True, "only": {"source": "in", "lines": [2]}})
    result, said = v2(tmp_path, made, caplog)
    assert result.counts["say"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}
    assert (tmp_path / "out.csv").read_bytes() == b"id\n2\n" and len(said) == 1


def test_job_with_a_warn_is_checked_without_a_word(caplog):
    with caplog.at_level(logging.DEBUG, logger="src.v2"):
        load_job(after(message="m"))
        load_job(through(message="m"))
    assert not [record for record in caplog.records if "] Code " in record.getMessage()]


@pytest.mark.parametrize("config, key", [({"priority": 0}, "priority"), ({"code": "x"}, "code"), ({"nope": 1}, "nope")])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(after(**config))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_both_v1_names_and_v2s_own(tmp_path, caplog):
    for at, kind in enumerate(("warn", "Warn", "tWarn")):
        (tmp_path / str(at)).mkdir()
        made = after(message="m")
        made["components"][2]["type"] = kind
        caplog.clear()
        assert v2(tmp_path / str(at), made, caplog)[1] == [("WARNING", "[say] Code 42: m")]


# ------------------------------------------------------------------
# What an independent review found (ticket 84)
# ------------------------------------------------------------------

def test_warn_that_is_to_hand_rows_on_and_gets_none_refuses_the_job():
    made = job([warn(outputs=("row2",), message="m"), writer("id:int")], [flow("row2", "say", "out")])
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("outputs", "a flow leaves it and none leads to it: it has no rows to hand on")]


def test_v1s_die_on_error_is_taken():
    load_job(after(message="m", die_on_error=False))


def test_fault_further_down_a_flow_with_a_warn_in_it_is_found_when_the_job_is_checked():
    made = through(message="m")
    step = {"id": "it", "type": "FilterRows", "inputs": ["row2"], "outputs": ["row3"],
            "config": {"conditions": [{"column": "nope", "function": "", "operator": "==", "value": "1"}]},
            "schema": {"input": columns("id:int"), "output": columns("id:int")}}
    made["components"].insert(2, step)
    made["components"][3]["inputs"] = ["row3"]
    made["flows"][1:] = [flow("row2", "say", "it"), flow("row3", "it", "out")]
    with pytest.raises(JobRefusedError, match="nope"):
        load_job(made)


def test_message_is_one_line_of_plain_ascii_in_the_log(tmp_path, caplog):
    _, said = v2(tmp_path, after(message="caf\u00e9\nnext"), caplog)
    assert said == [("WARNING", "[say] Code 42: caf\\xe9\\nnext")]
