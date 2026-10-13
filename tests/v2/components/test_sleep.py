"""Sleep: the job waits a number of seconds."""
import logging
import time

import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, reader

from .test_file_actions_kit import action, on_v2


def waiting(kind="Sleep", **config):
    return action("wait", kind, **config)


@pytest.fixture
def asked(monkeypatch):
    """How long each sleep was to last, with no time spent on it."""
    lengths = []
    monkeypatch.setattr(time, "sleep", lengths.append)
    return lengths


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# Waiting
# ------------------------------------------------------------------

@pytest.mark.parametrize("given, seconds, said", [("2", 2.0, "2 s"), (" 0.5 ", 0.5, "0.5 s"), (90, 90.0, "90 s"), (0, 0.0, "0 s")])
def test_job_waits_the_seconds_given_and_says_so_before_and_after(tmp_path, asked, caplog, given, seconds, said):
    caplog.set_level(logging.INFO, logger="src.v2")
    result = on_v2(job([waiting(pause_duration=given)], []), tmp_path)
    assert result.status == "success", result.error
    assert asked == [seconds]
    lines = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[wait]")]
    assert lines == [f"[wait] waiting {said}", f"[wait] waited {said}"]


def test_wait_stands_between_the_two_lines(tmp_path, monkeypatch):
    happened = []

    class Heard(logging.Handler):
        def emit(self, record):
            if record.getMessage().startswith("[wait]"):
                happened.append(record.getMessage())

    monkeypatch.setattr(time, "sleep", lambda seconds: happened.append(f"slept {seconds:g}"))
    heard, log = Heard(), logging.getLogger("src.v2")
    level = log.level
    log.addHandler(heard)
    log.setLevel(logging.INFO)
    try:
        on_v2(job([waiting(pause_duration=2)], []), tmp_path)
    finally:
        log.removeHandler(heard)
        log.setLevel(level)
    assert happened == ["[wait] waiting 2 s", "slept 2", "[wait] waited 2 s"]


def test_one_second_when_none_is_given_as_in_talend(tmp_path, asked):
    assert on_v2(job([waiting()], []), tmp_path).status == "success" and asked == [1.0]


def test_time_really_passes(tmp_path):
    started = time.monotonic()
    result = on_v2(job([waiting(pause_duration=0.2)], []), tmp_path)
    assert result.status == "success" and 0.2 <= time.monotonic() - started < 5


def test_seconds_from_the_context(tmp_path, asked):
    made = dict(job([waiting(pause_duration="${context.pause}")], []), context={"Default": {"pause": {"value": "3", "type": "str"}}})
    assert on_v2(made, tmp_path).status == "success" and asked == [3.0]


def test_context_value_that_is_no_number_fails_the_job_when_its_turn_comes(tmp_path, asked):
    made = dict(job([waiting(pause_duration="${context.pause}")], []), context={"Default": {"pause": {"value": "soon", "type": "str"}}})
    with pytest.raises(JobRefusedError) as refused:
        on_v2(made, tmp_path)
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("config", "pause_duration: expected a number, got 'soon'")]
    assert asked == []


def test_wait_for_each_pass_of_a_loop(tmp_path, asked):
    each = {"id": "each", "type": "Foreach", "config": {"values": ["a", "b", "c"]}, "inputs": [], "outputs": ["it"],
            "schema": {"input": [], "output": []}}
    made = job([each, waiting(pause_duration=4)], [])
    made["flows"].append({"name": "it", "from": "each", "to": "wait", "type": "iterate"})
    result = on_v2(made, tmp_path)
    assert result.status == "success", result.error
    assert asked == [4.0, 4.0, 4.0]


def test_wait_is_ended_at_once_by_whoever_stops_the_job(tmp_path, monkeypatch):
    def stopped(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", stopped)
    with pytest.raises(KeyboardInterrupt):
        on_v2(job([waiting(pause_duration=3600)], []), tmp_path)


def test_one_row_is_counted(tmp_path, asked):
    result = on_v2(dict(job([waiting(pause_duration=1)], []), run={"row_counts": True}), tmp_path)
    assert result.counts["wait"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}


# ------------------------------------------------------------------
# What is refused, and the names it goes by
# ------------------------------------------------------------------

@pytest.mark.parametrize("given, said", [
    ("soon", "expected a number, got 'soon'"),
    (-1, "-1 seconds is no time to wait; give zero or more"),
    ("-0.5", "-0.5 seconds is no time to wait; give zero or more"),
    ("nan", "nan seconds is no time to wait; give zero or more"),
    ("inf", "inf seconds is no time to wait; give zero or more"),
    (True, "expected a number, got True"),
])
def test_what_is_no_number_of_seconds_refuses_the_job(given, said):
    assert refusals(job([waiting(pause_duration=given)], [])) == [("pause_duration", said)]


def test_flow_to_it_refuses_the_job():
    made = job([reader("id:int"), dict(waiting(), inputs=["row1"])], [flow("row1", "in", "wait")])
    assert refusals(made) == [("inputs", "takes no input, but 1 flow arrives")]


def test_what_the_converter_writes_is_taken(tmp_path, asked):
    made = job([waiting(kind="SleepComponent", pause_duration="1", tstatcatcher_stats=False, label="x")], [])
    assert on_v2(made, tmp_path).status == "success" and asked == [1.0]


@pytest.mark.parametrize("kind", ["sleep", "Sleep", "SleepComponent", "tSleep"])
def test_every_name_of_it(tmp_path, asked, kind):
    assert on_v2(job([waiting(kind=kind, pause_duration=2)], []), tmp_path).status == "success" and asked == [2.0]
