"""Whole jobs of several subjobs, on v1 and on v2: triggers, context, counts."""
import pytest

from tests.v2.answer_key import assert_matches_v1, run_job, run_v2
from tests.v2.components.kit import flow, job, reader, writer

SCHEMA = "id:int, name:str"
DATA = b"1;a\n2;b\n3;c\n"


def copy_subjob(tag, source, target, **reader_config):
    """A reader and a writer, joined by one flow: one subjob."""
    return (
        [reader(SCHEMA, component_id=f"in_{tag}", path=source, outputs=(f"row_{tag}",), **reader_config),
         writer(SCHEMA, component_id=f"out_{tag}", path=target, inputs=(f"row_{tag}",), include_header=False)],
        [flow(f"row_{tag}", f"in_{tag}", f"out_{tag}")],
    )


def chain(*subjobs, triggers=(), **more):
    components, flows = [], []
    for subjob_components, subjob_flows in subjobs:
        components += subjob_components
        flows += subjob_flows
    return job(components, flows, triggers=list(triggers), **more)


def trigger(kind, source, target, **more):
    made = {"type": kind, "from": source, "to": target}
    made.update(more)
    return made


def same(tmp_path, job_config, inputs=None):
    run = assert_matches_v1(job_config, inputs or {"in.csv": DATA}, tmp_path)
    assert run.succeeded, run.error
    return run.files


def test_a_subjob_reads_what_the_one_before_it_wrote(tmp_path):
    made = chain(copy_subjob("b", "mid.csv", "end.csv"), copy_subjob("a", "in.csv", "mid.csv"),
                 triggers=[trigger("OnSubjobOk", "in_a", "in_b")])
    assert same(tmp_path, made)["end.csv"] == DATA


def test_on_component_ok_chains_subjobs_too(tmp_path):
    made = chain(copy_subjob("b", "mid.csv", "end.csv"), copy_subjob("a", "in.csv", "mid.csv"),
                 triggers=[trigger("OnComponentOk", "out_a", "in_b")])
    assert same(tmp_path, made)["end.csv"] == DATA


def test_subjobs_nothing_triggers_run_in_the_order_they_are_written(tmp_path):
    made = chain(copy_subjob("a", "in.csv", "out.csv"), copy_subjob("b", "other.csv", "out.csv"))
    files = same(tmp_path, made, {"in.csv": DATA, "other.csv": b"9;z\n"})
    assert files["out.csv"] == b"9;z\n"


@pytest.mark.parametrize(
    "condition, runs",
    [
        ('((Integer)globalMap.get("out_a_NB_LINE")) > 2', True),
        ('((Integer)globalMap.get("out_a_NB_LINE")) > 3', False),
        ('((Integer)globalMap.get("out_a_NB_LINE")) == 3 && context.go == "Y"', True),
        ('"N" == ${context.go}', False),
        ("context.limit >= 3", True),
        ("!(context.limit >= 3)", False),
    ],
)
def test_run_if_decides_from_counts_and_context(tmp_path, condition, runs):
    context = {"Default": {"go": {"value": "Y", "type": "str"}, "limit": {"value": "3", "type": "int"}}}
    made = chain(copy_subjob("a", "in.csv", "mid.csv"), copy_subjob("b", "mid.csv", "end.csv"),
                 triggers=[trigger("RunIf", "out_a", "in_b", condition=condition)], context=context)
    files = same(tmp_path, made)
    assert ("end.csv" in files) is runs


def test_triggers_of_one_subjob_fire_in_output_order(tmp_path):
    # Both targets write the same file; the one that runs last wins.
    made = chain(copy_subjob("a", "in.csv", "mid.csv"), copy_subjob("late", "in.csv", "out.csv"),
                 copy_subjob("early", "other.csv", "out.csv"),
                 triggers=[trigger("OnSubjobOk", "in_a", "in_late", output_id=2),
                           trigger("OnSubjobOk", "in_a", "in_early", output_id=1)])
    files = same(tmp_path, made, {"in.csv": DATA, "other.csv": b"9;z\n"})
    assert files["out.csv"] == DATA


def test_context_values_reach_paths_and_typed_keys(tmp_path):
    context = {"Default": {"dir": {"value": "data", "type": "str"}, "skip": {"value": "1", "type": "int"},
                           "sep": {"value": ";", "type": "str"}}}
    components, flows = copy_subjob("a", "${context.dir}/in.csv", "context.dir/out.csv",
                                    header_rows="context.skip", fieldseparator="${context.sep}")
    files = same(tmp_path, job(components, flows, context=context), {"data/in.csv": b"h;h\n" + DATA})
    assert files["data/out.csv"] == DATA


def failing_first(triggers):
    return chain(copy_subjob("a", "missing.csv", "mid.csv"), copy_subjob("ok", "in.csv", "ok.csv"),
                 copy_subjob("err", "in.csv", "err.csv"), triggers=triggers)


def after_failure(tmp_path, triggers):
    """Neither engine finishes these jobs, so files are not compared by the harness; v2's are checked here."""
    made = failing_first(triggers)
    assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    run = run_job(made, {"in.csv": DATA}, tmp_path / "again", run_v2)
    assert not run.succeeded
    return sorted(run.files)


def test_failed_subjob_fires_its_error_trigger_and_not_its_ok_trigger(tmp_path):
    triggers = [trigger("OnSubjobOk", "in_a", "in_ok"), trigger("OnSubjobError", "in_a", "in_err")]
    assert after_failure(tmp_path, triggers) == ["err.csv"]


def test_other_subjobs_still_run_after_a_failure(tmp_path):
    assert after_failure(tmp_path, []) == ["err.csv", "ok.csv"]


def test_on_component_error_fires_for_the_component_that_failed(tmp_path):
    triggers = [trigger("OnComponentOk", "in_a", "in_ok"), trigger("OnComponentError", "in_a", "in_err")]
    assert after_failure(tmp_path, triggers) == ["err.csv"]
