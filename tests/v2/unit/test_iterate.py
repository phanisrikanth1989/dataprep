"""An iterate link: what it leads to runs once for each item of the component it leaves."""
import logging

import pytest

from src.v2.errors import JobRefusedError
from src.v2.job.loader import load_job

from .kit import REGISTRY, Note, Once, job, lines, run

VALUE = '((String)globalMap.get("each_CURRENT_VALUE"))'


@pytest.fixture(autouse=True)
def fresh():
    Note.said.clear()
    Once.made = 0


def looped(values, *more, flows=(), triggers=(), **config):
    """each (the values) -iterate-> note (says the value), and more components, flows and triggers."""
    components = [("each", "each", {"values": list(values), **config}), ("note", "note", {"say": VALUE}), *more]
    made = job(components, [("it", "each", "note", "iterate"), *flows])
    made["triggers"] = [{"type": kind, "from": source, "to": target, **({"condition": extra[0]} if extra else {})}
                        for kind, source, target, *extra in triggers]
    return made


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made, registry=REGISTRY)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# A pass for each item
# ------------------------------------------------------------------

def test_body_runs_once_for_each_item_in_order_with_the_item_in_globalmap():
    result = run(looped(["a", "b", "c"]))
    assert result.status == "success", result.error
    assert Note.said == ["a", "b", "c"]
    assert result.global_map["each_CURRENT_VALUE"] == "c" and result.global_map["each_CURRENT_ITERATION"] == 3


def test_what_the_body_sets_off_runs_in_every_pass(tmp_path):
    more = [("then", "note", {"say": '"then " + ' + VALUE}), ("last", "note", {"say": '"last " + ' + VALUE})]
    made = looped(["a", "b"], *more, triggers=[("OnSubjobOk", "note", "then"), ("OnComponentOk", "then", "last")])
    assert run(made).status == "success"
    assert Note.said == ["a", "then a", "last a", "b", "then b", "last b"]


def test_files_of_a_pass_are_in_place_when_the_pass_ends(tmp_path):
    path = '"' + str(tmp_path) + '/out_" + ' + VALUE + ' + ".csv"'
    more = [("in", "rows", {"data": {"n": [1, 2]}}), ("out", "save", {"path": "{{java}}" + path}),
            ("seen", "note", {"say": "{{java}}" + path})]
    made = job([("each", "each", {"values": ["a", "b"]}), *more],
               [("it", "each", "in", "iterate"), ("r1", "in", "out", "flow")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "in", "to": "seen"}]
    result = run(made)
    assert result.status == "success", result.error
    assert Note.said == [f"{tmp_path}/out_a.csv", f"{tmp_path}/out_b.csv"]
    assert lines(tmp_path / "out_a.csv") == lines(tmp_path / "out_b.csv") == ["n", "1", "2"]


def test_trigger_of_the_looping_component_fires_once_when_the_loop_is_over():
    made = looped(["a", "b"], ("after", "note", {"say": "after"}), triggers=[("OnSubjobOk", "each", "after")])
    assert run(made).status == "success"
    assert Note.said == ["a", "b", "after"]


def test_no_item_no_pass_and_the_triggers_of_the_looping_component_fire(caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    made = looped([], ("after", "note", {"say": "after"}), triggers=[("OnSubjobOk", "each", "after")])
    result = run(made)
    assert result.status == "success" and Note.said == ["after"]
    assert "[each] no item: what it leads to is not run" in [record.getMessage() for record in caplog.records]


def test_looping_component_that_made_no_list_runs_no_pass():
    made = looped(["a"], ("after", "note", {"say": "after"}), triggers=[("OnSubjobOk", "each", "after")], gives_up=True)
    result = run(made)
    assert result.status == "success" and Note.said == ["after"]
    assert "loops" not in result.summary()


def test_looping_component_that_nothing_is_linked_to_just_runs():
    result = run(job([("each", "each", {"values": ["a"]})], []))
    assert result.status == "success" and Note.said == []


def test_items_may_be_made_one_at_a_time_as_their_passes_come_and_are_put_away_when_the_loop_is_over():
    result = run(looped(["a", "b"], one_at_a_time=True))
    assert result.status == "success", result.error
    assert Note.said == ["made a", "a", "made b", "b", "put away"]
    assert result.summary()["loops"] == {"each": {"items": 2, "passes": 2}}


def test_items_are_put_away_also_when_a_pass_fails_when_there_are_too_many_and_when_nothing_loops_over_them(tmp_path):
    made = looped(["a", "b"], ("boom", "boom", {}), ("out", "save", {"path": str(tmp_path / "o.csv")}),
                  flows=[("r1", "boom", "out", "flow")], triggers=[("OnSubjobOk", "note", "boom")], one_at_a_time=True)
    assert run(made).status == "failed"
    assert Note.said == ["made a", "a", "put away"]
    Note.said.clear()
    assert run(looped(["a", "b"], one_at_a_time=True, max_items=1)).status == "failed"
    assert Note.said == ["put away"]
    Note.said.clear()
    assert run(job([("each", "each", {"values": ["a"], "one_at_a_time": True})], [])).status == "success"
    assert Note.said == ["put away"]


def test_loop_in_a_loop():
    components = [("outer", "each", {"values": ["x", "y"]}), ("each", "each", {"values": [1, 2]}),
                  ("note", "note", {"say": '((String)globalMap.get("outer_CURRENT_VALUE")) + ' + VALUE})]
    made = job(components, [("it1", "outer", "each", "iterate"), ("it2", "each", "note", "iterate")])
    assert run(made).status == "success"
    assert Note.said == ["x1", "x2", "y1", "y2"]


def test_what_a_source_made_in_one_pass_is_made_again_in_the_next(tmp_path):
    path = '{{java}}"' + str(tmp_path) + '/" + ' + VALUE + ' + ".csv"'
    made = job([("each", "each", {"values": ["a", "b"]}), ("in", "once", {}), ("out", "save", {"path": path})],
               [("it", "each", "in", "iterate"), ("r1", "in", "out", "flow")])
    assert run(made).status == "success"
    assert (lines(tmp_path / "a.csv"), lines(tmp_path / "b.csv")) == (["n", "1"], ["n", "2"])


# ------------------------------------------------------------------
# What is said and counted
# ------------------------------------------------------------------

def test_log_names_every_pass_and_the_end_of_the_loop(caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    run(looped(["a", "b"]))
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[each]")]
    assert said[:2] == ["[each] item 1 of 2: a", "[each] item 2 of 2: b"]
    assert said[2].startswith("[each] 2 items done in ")


def test_row_count_in_globalmap_is_the_pass_own_and_the_summary_has_the_sum(tmp_path):
    more = [("in", "rows", {"data": {"n": [1, 2, 3]}}), ("out", "save", {"path": str(tmp_path / "o.csv")}),
            ("seen", "note", {"say": '((Integer)globalMap.get("out_NB_LINE"))'})]
    made = job([("each", "each", {"values": ["a", "b"]}), *more],
               [("it", "each", "in", "iterate"), ("r1", "in", "out", "flow")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "in", "to": "seen"}]
    result = run(made, row_counts=True)
    assert result.status == "success", result.error
    assert Note.said == [3, 3]
    assert result.rows == {"out": 6}
    assert result.counts["in"] == {"NB_LINE": 6, "NB_LINE_OK": 6, "NB_LINE_REJECT": 0}
    assert result.summary()["loops"] == {"each": {"items": 2, "passes": 2}}


def test_row_count_left_in_globalmap_when_the_loop_is_over_is_the_last_pass_own(tmp_path):
    more = [("in", "rows", {"data": {"n": [1, 2, 3]}}), ("out", "save", {"path": str(tmp_path / "o.csv")})]
    made = job([("each", "each", {"values": ["a", "b"]}), *more], [("it", "each", "in", "iterate"), ("r1", "in", "out", "flow")])
    result = run(made)
    assert result.rows == {"out": 6} and result.global_map["out_NB_LINE"] == 3


# ------------------------------------------------------------------
# A pass that fails, and a die
# ------------------------------------------------------------------

def failing_at_b(tmp_path, *more, triggers=()):
    """each (a, b, c) -iterate-> a reader of <value>.csv -> a file; only a.csv and c.csv are there."""
    for name in ("a", "c"):
        (tmp_path / f"{name}.csv").write_text("n\n1\n")
    path = '{{java}}"' + str(tmp_path) + '/" + ' + VALUE + ' + ".csv"'
    components = [("each", "each", {"values": ["a", "b", "c"]}), ("in", "from_file", {"path": path}),
                  ("out", "save", {"path": str(tmp_path / "out.csv")}), ("seen", "note", {"say": VALUE}), *more]
    made = job(components, [("it", "each", "in", "iterate"), ("r1", "in", "out", "flow")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "in", "to": "seen"}] + [
        {"type": kind, "from": source, "to": target} for kind, source, target in triggers]
    return made


def test_pass_that_fails_stops_the_loop_and_fails_the_looping_component(tmp_path):
    result = run(failing_at_b(tmp_path))
    assert result.status == "failed" and Note.said == ["a"]
    assert result.failed_component == "in" and list(result.failures) == ["in", "each"]
    assert result.failures["each"] == f"its loop stopped at item 2 of 3 (b): in failed: {result.failures['in']}"
    assert result.summary()["loops"] == {"each": {"items": 3, "passes": 2, "failed_item": "b"}}


def test_error_triggers_fire_in_the_pass_that_failed_and_for_the_looping_component(tmp_path):
    more = [("in_pass", "note", {"say": "handled in the pass"}), ("after", "note", {"say": "handled after"}),
            ("fine", "note", {"say": "the loop was fine"})]
    made = failing_at_b(tmp_path, *more, triggers=[("OnSubjobError", "in", "in_pass"), ("OnSubjobError", "each", "after"),
                                                    ("OnSubjobOk", "each", "fine")])
    assert run(made).status == "failed"
    assert Note.said == ["a", "handled in the pass", "handled after"]


def test_die_in_a_body_ends_the_job(tmp_path):
    components = [("each", "each", {"values": ["a", "b"]}), ("note", "note", {"say": VALUE}), ("die", "stop", {}),
                  ("after", "note", {"say": "after"})]
    made = job(components, [("it", "each", "note", "iterate")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "note", "to": "die"}, {"type": "OnSubjobOk", "from": "each", "to": "after"},
                        {"type": "OnSubjobError", "from": "each", "to": "after"}]
    result = run(made)
    assert result.status == "failed" and result.failed_component == "die"
    assert Note.said == ["a"]


def test_more_items_than_the_cap_fail_the_job_before_the_first_pass():
    result = run(looped(["a", "b", "c"], max_items=2))
    assert result.status == "failed" and Note.said == []
    assert result.error == "3 items, and a loop may have 2 by `max_items`: none is run"
    assert run(looped(["a", "b"], max_items=2)).status == "success"


# ------------------------------------------------------------------
# What is refused when the job loads
# ------------------------------------------------------------------

def test_cap_of_no_item_at_all_is_refused():
    assert refusals(looped(["a"], max_items=0)) == [("max_items", "a loop of at most 0 items is none; give 1 or more")]


def test_iterate_link_from_a_component_that_starts_no_loop_is_refused():
    made = job([("in", "rows", {"data": {"n": [1]}}), ("note", "note", {})], [("it", "in", "note", "iterate")])
    assert refusals(made) == [("flows[0].type", "a rows starts no loop: an iterate link leaves a component that makes a "
                                                "list of items")]


def test_iterate_link_to_a_component_that_takes_rows_is_refused():
    components = [("each", "each", {}), ("in", "rows", {"data": {"n": [1]}}), ("add", "add", {}), ("out", "save", {"path": "o"})]
    made = job(components, [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow"), ("it", "each", "add", "iterate")])
    assert refusals(made) == [("flows[2].to", "an iterate link leads to the start of a subjob, and 'add' takes rows "
                                              "from 'in'")]


def test_two_iterate_links_from_one_component_or_to_one_component_are_refused():
    components = [("each", "each", {}), ("other", "each", {}), ("note", "note", {}), ("more", "note", {})]
    made = job(components, [("it1", "each", "note", "iterate"), ("it2", "each", "more", "iterate")])
    assert refusals(made) == [("flows[1].from", "'each' has an iterate link already, to 'note': a loop has one body")]
    made = job(components, [("it1", "each", "note", "iterate"), ("it2", "other", "note", "iterate")])
    assert refusals(made) == [("flows[1].to", "'note' is the start of the loop of 'each' already")]


def test_trigger_from_outside_into_a_body_is_refused():
    components = [("each", "each", {}), ("note", "note", {}), ("then", "note", {}), ("outside", "note", {})]
    made = job(components, [("it", "each", "note", "iterate")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "note", "to": "then"}, {"type": "OnSubjobOk", "from": "outside", "to": "then"}]
    assert refusals(made) == [("triggers[1]", "'then' is run by the loop of 'each', once for each item: a trigger from "
                                                  "'outside', which is not, cannot set it off")]


def test_body_that_leads_back_to_its_own_loop_is_refused():
    components = [("each", "each", {}), ("note", "note", {})]
    made = job(components, [("it", "each", "note", "iterate")])
    made["triggers"] = [{"type": "OnSubjobOk", "from": "note", "to": "each"}]
    assert refusals(made) == [("triggers[0]", "'each' starts the loop that runs 'note': a trigger from inside the loop "
                                                  "cannot set it off again")]


def test_keys_talend_has_for_passes_side_by_side_are_taken_and_said_to_have_no_effect(caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    made = looped(["a", "b"])
    made["flows"][0].update({"enable_parallel": True, "number_parallel": 4})
    assert run(made).status == "success" and Note.said == ["a", "b"]
    assert "[each] the passes run one after another: v2 does not run them side by side" in [
        record.getMessage() for record in caplog.records]


def test_run_for_picked_rows_of_a_reader_inside_a_loop_is_refused(tmp_path):
    made = failing_at_b(tmp_path)
    made["run"] = {"only": {"source": "in", "rows": [1]}}
    with pytest.raises(JobRefusedError) as refused:
        run(made)
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("run.only.source", "'in' is run by the loop of 'each', once for each item: a run for picked rows of such a "
                            "reader is not built yet")]
