"""Triggers: which subjob runs after which, and what a failure sets off."""
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
