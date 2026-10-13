"""Triggers: which subjob runs after which, and what a failure sets off."""
import logging

import pytest

from src.v2.errors import JobRefusedError

from .kit import Mark, job, run


def marks(*names):
    return [(name, "mark", {"name": name}) for name in names]


def trigger(kind, source, target, **more):
    made = {"type": kind, "from": source, "to": target}
    made.update(more)
    return made


def ran(job_config, **kwargs):
    Mark.ran.clear()
    result = run(job_config, **kwargs)
    return list(Mark.ran), result


def test_subjobs_nothing_triggers_run_in_job_config_order():
    order, _ = ran(job(marks("a", "b", "c"), []))
    assert order == ["a", "b", "c"]


def test_triggered_subjob_waits_for_its_trigger():
    order, _ = ran(job(marks("late", "first"), [], triggers=[trigger("OnSubjobOk", "first", "late")]))
    assert order == ["first", "late"]


def test_triggered_subjobs_run_depth_first_before_the_next_one():
    triggers = [trigger("OnSubjobOk", "root", "b1"), trigger("OnSubjobOk", "root", "b2"),
                trigger("OnSubjobOk", "b1", "b1_child")]
    order, _ = ran(job(marks("root", "b1", "b1_child", "b2", "other"), [], triggers=triggers))
    assert order == ["root", "b1", "b1_child", "b2", "other"]


def test_triggers_of_one_subjob_fire_in_output_order():
    triggers = [trigger("OnSubjobOk", "root", "second", output_id=2), trigger("OnSubjobOk", "root", "first", output_id=1)]
    order, _ = ran(job(marks("root", "second", "first"), [], triggers=triggers))
    assert order == ["root", "first", "second"]


def test_a_subjob_runs_once_however_many_triggers_point_at_it():
    triggers = [trigger("OnSubjobOk", "a", "c"), trigger("OnSubjobOk", "b", "c")]
    order, _ = ran(job(marks("a", "b", "c"), [], triggers=triggers))
    assert order == ["a", "c", "b"]


def test_on_component_ok_fires_when_the_subjob_finished():
    order, _ = ran(job(marks("a", "b"), [], triggers=[trigger("OnComponentOk", "a", "b")]))
    assert order == ["a", "b"]


def failing(triggers, extra=()):
    components = [("bad", "boom", {"why": "it broke"}), *marks("ok_next", "error_next", *extra)]
    return job(components, [], triggers=triggers)


def test_failed_subjob_sets_off_its_error_triggers_only():
    triggers = [trigger("OnSubjobOk", "bad", "ok_next"), trigger("OnSubjobError", "bad", "error_next")]
    order, result = ran(failing(triggers))
    assert order == ["error_next"]
    assert result.status == "failed"
    assert result.failed_component == "bad"
    assert "it broke" in result.error


def test_on_component_error_fires_for_the_component_that_failed():
    triggers = [trigger("OnComponentOk", "bad", "ok_next"), trigger("OnComponentError", "bad", "error_next")]
    order, _ = ran(failing(triggers))
    assert order == ["error_next"]


def test_on_component_error_of_a_healthy_component_does_not_fire(tmp_path):
    components = [("in", "rows", {"data": {"n": [1]}}), ("add", "add", {"column": "missing"}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")}), *marks("for_in", "for_add")]
    flows = [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")]
    triggers = [trigger("OnComponentError", "in", "for_in"), trigger("OnComponentError", "add", "for_add")]
    order, _ = ran(job(components, flows, triggers=triggers))
    assert order == ["for_add"]


def test_other_subjobs_still_run_after_one_failed():
    order, result = ran(job([*marks("a"), ("bad", "boom", {}), *marks("b")], []))
    assert order == ["a", "b"]
    assert result.status == "failed"
    assert list(result.failures) == ["bad"]


def test_the_first_failure_is_the_one_reported():
    _, result = ran(job([("one", "boom", {"why": "first"}), ("two", "boom", {"why": "second"})], []))
    assert result.failed_component == "one" and "first" in result.error
    assert list(result.failures) == ["one", "two"]


def test_run_if_fires_on_a_true_condition_only():
    triggers = [trigger("RunIf", "a", "yes", condition="context.go == 'Y'"),
                trigger("RunIf", "a", "no", condition="context.go == 'N'")]
    order, _ = ran(job(marks("a", "yes", "no"), [], triggers=triggers, context={"go": "Y"}))
    assert order == ["a", "yes"]


def test_run_if_can_read_what_the_subjob_before_it_counted(tmp_path):
    components = [("in", "rows", {"data": {"n": [1, 2, 3]}}), ("out", "save", {"path": str(tmp_path / "o.csv")}),
                  *marks("many", "none")]
    triggers = [trigger("RunIf", "out", "many", condition='((Integer)globalMap.get("out_NB_LINE")) > 2'),
                trigger("RunIf", "out", "none", condition='((Integer)globalMap.get("out_NB_LINE")) == 0')]
    order, _ = ran(job(components, [("r1", "in", "out", "flow")], triggers=triggers))
    assert order == ["many"]


def test_run_if_is_evaluated_after_a_failed_subjob_too():
    triggers = [trigger("RunIf", "bad", "ok_next", condition="true"), trigger("OnSubjobOk", "bad", "error_next")]
    order, _ = ran(failing(triggers))
    assert order == ["ok_next"]


def test_run_if_that_cannot_be_evaluated_stops_the_job():
    triggers = [trigger("RunIf", "a", "b", condition="context.nope == 1")]
    order, result = ran(job(marks("a", "b", "c"), [], triggers=triggers))
    assert order == ["a"]
    assert result.status == "failed"
    assert "context.nope == 1" in result.error


def test_trigger_inside_one_subjob_is_refused(tmp_path):
    components = [("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": str(tmp_path / "o.csv")})]
    with pytest.raises(JobRefusedError) as caught:
        run(job(components, [("r1", "in", "out", "flow")], triggers=[trigger("OnSubjobOk", "in", "out")]))
    assert "same subjob" in caught.value.report.format()


def test_triggers_that_form_a_loop_are_refused():
    triggers = [trigger("OnSubjobOk", "a", "b"), trigger("OnSubjobOk", "b", "a")]
    with pytest.raises(JobRefusedError) as caught:
        run(job(marks("a", "b"), [], triggers=triggers))
    assert "loop" in caught.value.report.format()


def test_v1_spellings_of_the_trigger_ends_are_accepted():
    triggers = [{"type": "OnSubjobOk", "from_component": "first", "to_component": "late"}]
    order, _ = ran(job(marks("late", "first"), [], triggers=triggers))
    assert order == ["first", "late"]


# ------------------------------------------------------------------
# What the log says of triggers
# ------------------------------------------------------------------

def trigger_lines(caplog, job_config, **kwargs):
    """The lines a run logs about its triggers, and the order its marks ran in."""
    caplog.set_level(logging.INFO, logger="src.v2")
    caplog.clear()
    order, _ = ran(job_config, **kwargs)
    said = [record for record in caplog.records if record.name == "src.v2.engine.runner"]
    return [record.getMessage() for record in said if "] trigger " in record.getMessage()], order


def counted_job(tmp_path, condition, source="in"):
    """Three rows written by `out`, and a RunIf on a count leaving `in` or `out` for the mark `after`."""
    components = [("in", "rows", {"data": {"n": [1, 2, 3]}}), ("out", "save", {"path": str(tmp_path / "o.csv")}),
                  *marks("after")]
    triggers = [trigger("RunIf", source, "after", condition=condition)]
    return job(components, [("r1", "in", "out", "flow")], triggers=triggers)


def test_trigger_that_fires_is_logged_with_its_type_and_both_ends(caplog):
    lines, _ = trigger_lines(caplog, job(marks("late", "first"), [], triggers=[trigger("OnSubjobOk", "first", "late")]))
    assert lines == ["[t] trigger OnSubjobOk from first to late fired: the subjob of late is set off"]


def test_trigger_line_is_logged_at_info(caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    ran(job(marks("a", "b"), [], triggers=[trigger("OnComponentOk", "a", "b")]))
    (record,) = [record for record in caplog.records if "] trigger " in record.getMessage()]
    assert record.levelno == logging.INFO
    assert record.getMessage() == "[t] trigger OnComponentOk from a to b fired: the subjob of b is set off"


def test_trigger_that_does_not_fire_is_not_logged(caplog):
    triggers = [trigger("OnSubjobOk", "bad", "ok_next"), trigger("OnSubjobError", "bad", "error_next")]
    lines, order = trigger_lines(caplog, failing(triggers))
    assert lines == ["[t] trigger OnSubjobError from bad to error_next fired: the subjob of error_next is set off"]
    assert order == ["error_next"]


def test_on_component_error_that_fires_is_logged(caplog):
    triggers = [trigger("OnComponentOk", "bad", "ok_next"), trigger("OnComponentError", "bad", "error_next")]
    lines, _ = trigger_lines(caplog, failing(triggers))
    assert lines == ["[t] trigger OnComponentError from bad to error_next fired: the subjob of error_next is set off"]


def test_run_if_is_logged_each_time_it_is_judged_with_what_it_came_to(caplog, tmp_path):
    # The count of `out` is not there yet when `in` is done; it is when the subjob is.
    condition = '((Integer)globalMap.get("out_NB_LINE")) > 0'
    lines, order = trigger_lines(caplog, counted_job(tmp_path, condition))
    assert lines == [
        f"[t] trigger RunIf from in to after, judged when in was done: {condition} is false",
        f"[t] trigger RunIf from in to after, judged when the subjob was done: {condition} is true: "
        "the subjob of after is set off",
    ]
    assert order == ["after"]


def test_run_if_that_stays_false_is_logged_both_times_and_sets_nothing_off(caplog, tmp_path):
    condition = '((Integer)globalMap.get("out_NB_LINE")) > 3'
    lines, order = trigger_lines(caplog, counted_job(tmp_path, condition))
    assert lines == [
        f"[t] trigger RunIf from in to after, judged when in was done: {condition} is false",
        f"[t] trigger RunIf from in to after, judged when the subjob was done: {condition} is false",
    ]
    assert order == []


def test_run_if_that_is_true_when_its_component_is_done_is_judged_once(caplog, tmp_path):
    condition = '((Integer)globalMap.get("out_NB_LINE")) > 2'
    lines, order = trigger_lines(caplog, counted_job(tmp_path, condition, source="out"))
    assert lines == [
        f"[t] trigger RunIf from out to after, judged when out was done: {condition} is true: "
        "the subjob of after is set off",
    ]
    assert order == ["after"]


def test_subjob_trigger_that_fires_when_the_subjob_is_done_is_logged(caplog):
    # b2 was set off by root already, so b1's trigger to it fires only when b1's subjob is gone through again.
    triggers = [trigger("OnSubjobOk", "root", "b1"), trigger("OnSubjobOk", "root", "b2"),
                trigger("OnSubjobOk", "b1", "b2")]
    lines, order = trigger_lines(caplog, job(marks("root", "b1", "b2"), [], triggers=triggers))
    assert lines == [
        "[t] trigger OnSubjobOk from root to b1 fired: the subjob of b1 is set off",
        "[t] trigger OnSubjobOk from root to b2 fired: the subjob of b2 is set off",
        "[t] trigger OnSubjobOk from b1 to b2 fired: the subjob of b2 is set off",
    ]
    assert order == ["root", "b1", "b2"]


def test_error_trigger_that_fires_when_the_subjob_is_done_is_logged(caplog):
    # As above, with b1 failing: its error trigger points at a subjob root has set off already.
    components = [*marks("root"), ("b1", "boom", {"why": "it broke"}), *marks("b2")]
    triggers = [trigger("OnSubjobOk", "root", "b1"), trigger("OnSubjobOk", "root", "b2"),
                trigger("OnSubjobError", "b1", "b2")]
    lines, order = trigger_lines(caplog, job(components, [], triggers=triggers))
    assert lines[-1] == "[t] trigger OnSubjobError from b1 to b2 fired: the subjob of b2 is set off"
    assert order == ["root", "b2"]


def test_trigger_line_is_one_line_of_plain_ascii(caplog):
    condition = "(context.go == 'caf\u00e9'\n    or True)"
    lines, order = trigger_lines(caplog, job(marks("a", "b"), [], triggers=[trigger("RunIf", "a", "b", condition=condition)],
                                             context={"go": "x"}))
    assert lines == ["[t] trigger RunIf from a to b, judged when a was done: (context.go == 'caf\\xe9' or True) is true: "
                     "the subjob of b is set off"]
    assert order == ["a", "b"]


def test_trigger_line_is_plain_ascii_whatever_the_component_ids_hold(caplog):
    made = job(marks("s\u00fcd", "nord"), [], triggers=[trigger("OnSubjobOk", "s\u00fcd", "nord")])
    lines, order = trigger_lines(caplog, made)
    assert lines == ["[t] trigger OnSubjobOk from s\\xfcd to nord fired: the subjob of nord is set off"]
    assert order == ["s\u00fcd", "nord"]
