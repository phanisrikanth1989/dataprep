"""The three parts of a job: what a prejob sets off, the job itself, what a postjob sets off."""
import logging

import pytest

from src.v2.components.control.postjob import Postjob
from src.v2.components.control.prejob import Prejob
from src.v2.errors import JobRefusedError
from src.v2.job.loader import load_job

from .kit import REGISTRY, Note, job, run

for _cls in (Prejob, Postjob):
    if REGISTRY.get(_cls.names[0]) is None:
        REGISTRY.register(_cls)

# Written in an order that is not the order they run in: the job itself first, its clean-up next, its set-up last.
EDGES = [("post", "postjob", {}), ("clean", "note", {"say": "clean"}), ("pre", "prejob", {}), ("setup", "note", {"say": "setup"})]
SET_OFF = [("OnComponentOk", "pre", "setup"), ("OnComponentOk", "post", "clean")]


@pytest.fixture(autouse=True)
def fresh():
    Note.said.clear()


def made(components, flows=(), triggers=SET_OFF):
    built = job(components, list(flows))
    built["triggers"] = [{"type": kind, "from": source, "to": target} for kind, source, target in triggers]
    return built


def failing(tmp_path):
    """A subjob that fails: a source that cannot be read, and the file it would have gone to."""
    return [("main", "boom", {"why": "no luck"}), ("out", "save", {"path": str(tmp_path / "o.csv")})], [("r1", "main", "out", "flow")]


def refusals(config):
    with pytest.raises(JobRefusedError) as refused:
        load_job(config, registry=REGISTRY)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# The order
# ------------------------------------------------------------------

def test_set_up_runs_first_and_clean_up_last_wherever_they_are_written():
    result = run(made([("main", "note", {"say": "main"}), *EDGES, ("more", "note", {"say": "more"})]))
    assert result.status == "success", result.error
    assert Note.said == ["setup", "main", "more", "clean"]


def test_job_without_them_runs_as_it_always_did():
    assert run(made([("a", "note", {"say": "a"}), ("b", "note", {"say": "b"})], triggers=[])).status == "success"
    assert Note.said == ["a", "b"]


def test_every_prejob_runs_before_the_job_and_every_postjob_after_it_in_the_order_written():
    components = [("main", "note", {"say": "main"}), *EDGES, ("post2", "postjob", {}), ("clean2", "note", {"say": "clean2"}),
                  ("pre2", "prejob", {}), ("setup2", "note", {"say": "setup2"})]
    triggers = [*SET_OFF, ("OnComponentOk", "pre2", "setup2"), ("OnComponentOk", "post2", "clean2")]
    assert run(made(components, triggers=triggers)).status == "success"
    assert Note.said == ["setup", "setup2", "main", "clean", "clean2"]


def test_what_a_prejob_sets_off_may_set_off_more_before_the_job_starts():
    components = [("main", "note", {"say": "main"}), *EDGES, ("then", "note", {"say": "then"})]
    assert run(made(components, triggers=[*SET_OFF, ("OnSubjobOk", "setup", "then")])).status == "success"
    assert Note.said == ["setup", "then", "main", "clean"]


def test_subjob_that_two_parts_of_the_job_set_off_runs_once():
    components = [("main", "note", {"say": "main"}), *EDGES, ("both", "note", {"say": "both"})]
    triggers = [*SET_OFF, ("OnSubjobOk", "setup", "both"), ("OnSubjobOk", "main", "both"), ("OnSubjobOk", "clean", "both")]
    assert run(made(components, triggers=triggers)).status == "success"
    assert Note.said == ["setup", "both", "main", "clean"]


# ------------------------------------------------------------------
# Clean-up runs whatever happened
# ------------------------------------------------------------------

def test_clean_up_runs_after_the_job_failed_and_the_job_has_failed_for_its_first_reason(tmp_path):
    components, flows = failing(tmp_path)
    result = run(made([*components, *EDGES], flows))
    assert Note.said == ["setup", "clean"]
    assert (result.status, result.error, result.failed_component) == ("failed", "no luck", "main")


def test_clean_up_runs_also_after_a_fault_no_component_answers_for_and_the_fault_goes_on(monkeypatch):
    # A fault of the engine itself, or of the machine: it is no failure of a component, and it is not hidden.
    from src.v2.engine.runner import Runner

    really = Runner._run_subjob

    def trips(self, members):
        if "main" in members:
            raise MemoryError("no memory left")
        return really(self, members)

    monkeypatch.setattr(Runner, "_run_subjob", trips)
    with pytest.raises(MemoryError, match="no memory left"):
        run(made([("main", "note", {"say": "main"}), *EDGES]))
    assert Note.said == ["setup", "clean"]


def test_clean_up_runs_after_a_die_and_nothing_else_does():
    components = [("main", "stop", {}), ("later", "note", {"say": "later"}), *EDGES]
    result = run(made(components))
    assert Note.said == ["setup", "clean"]
    assert (result.status, result.error) == ("failed", "stopped")


def test_clean_up_that_fails_fails_the_job(tmp_path):
    components, flows = failing(tmp_path)
    edges = [("post", "postjob", {}), *components]
    result = run(made([("job", "note", {"say": "job"}), *edges], flows, triggers=[("OnComponentOk", "post", "main")]))
    assert Note.said == ["job"]
    assert (result.status, result.error, result.failed_component) == ("failed", "no luck", "main")


def test_clean_up_that_fails_after_the_job_failed_does_not_hide_why_the_job_failed(tmp_path):
    components, flows = failing(tmp_path)
    more = [("post", "postjob", {}), ("worse", "boom", {"why": "and the clean-up too"}),
            ("out2", "save", {"path": str(tmp_path / "o2.csv")})]
    result = run(made([*components, *more], [*flows, ("r2", "worse", "out2", "flow")],
                      triggers=[("OnComponentOk", "post", "worse")]))
    assert (result.status, result.error, result.failed_component) == ("failed", "no luck", "main")
    assert result.failures == {"main": "no luck", "worse": "and the clean-up too"}


def test_die_in_the_clean_up_ends_the_clean_up():
    components = [("job", "note", {"say": "job"}), ("post", "postjob", {}), ("end", "stop", {}),
                  ("post2", "postjob", {}), ("never", "note", {"say": "never"})]
    result = run(made(components, triggers=[("OnComponentOk", "post", "end"), ("OnComponentOk", "post2", "never")]))
    assert Note.said == ["job"] and (result.status, result.error) == ("failed", "stopped")


# ------------------------------------------------------------------
# A set-up that fails
# ------------------------------------------------------------------

def test_job_is_not_run_when_its_set_up_failed_and_the_clean_up_is(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    components, flows = failing(tmp_path)
    edges = [("post", "postjob", {}), ("clean", "note", {"say": "clean"}), ("pre", "prejob", {})]
    result = run(made([("job", "note", {"say": "job"}), *edges, *components], flows,
                      triggers=[("OnComponentOk", "pre", "main"), ("OnComponentOk", "post", "clean")]))
    assert Note.said == ["clean"]
    assert (result.status, result.error, result.failed_component) == ("failed", "no luck", "main")
    assert "[t] the job itself is not run: what its prejob set off failed" in [record.getMessage() for record in caplog.records]


def test_job_is_not_run_when_its_set_up_ended_in_a_die_and_the_clean_up_is(caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    components = [("job", "note", {"say": "job"}), ("post", "postjob", {}), ("clean", "note", {"say": "clean"}),
                  ("pre", "prejob", {}), ("end", "stop", {})]
    result = run(made(components, triggers=[("OnComponentOk", "pre", "end"), ("OnComponentOk", "post", "clean")]))
    assert Note.said == ["clean"] and (result.status, result.error) == ("failed", "stopped")


def test_nothing_is_said_of_a_job_that_was_not_there_to_run(caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    result = run(made([("pre", "prejob", {}), ("end", "stop", {})], triggers=[("OnComponentOk", "pre", "end")]))
    assert result.status == "failed"
    assert not [record.getMessage() for record in caplog.records if "is not run" in record.getMessage()]


# ------------------------------------------------------------------
# What is refused
# ------------------------------------------------------------------

def test_nothing_leads_to_where_a_job_starts_or_to_where_its_clean_up_does():
    components = [("a", "note", {"say": "a"}), ("pre", "prejob", {}), ("post", "postjob", {}),
                  ("each", "each", {"values": ["x"]})]
    config = made(components, triggers=[("OnSubjobOk", "a", "pre"), ("OnSubjobOk", "a", "post")])
    assert refusals(config) == [
        ("triggers[0].to", "'pre' is a prejob: it is where a job's set-up starts, and nothing leads to it"),
        ("triggers[1].to", "'post' is a postjob: it is where a job's clean-up starts, and nothing leads to it")]
    looped = job(components, [("it", "each", "pre", "iterate")])
    assert refusals(looped) == [
        ("flows[0].to", "'pre' is a prejob: it is where a job's set-up starts, and nothing leads to it")]
