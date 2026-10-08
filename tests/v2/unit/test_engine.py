"""The engine: subjobs built as one lazy plan each and run in one pass."""
import polars as pl
import pytest

from src.v2.components.base import Source
from src.v2.components.registry import Registry
from src.v2.engine import run_job
from src.v2.errors import JobFailedError, JobRefusedError
from src.v2.job.keys import Key

from .kit import Add, Peek, Save, job, lines, run


# ------------------------------------------------------------------
# One subjob
# ------------------------------------------------------------------

def test_rows_flow_from_source_through_transform_to_sink(tmp_path):
    out = tmp_path / "out.csv"
    result = run(job(
        [("in", "rows", {"data": {"n": [1, 2, 3]}}), ("add", "add", {"amount": 10}), ("out", "save", {"path": str(out)})],
        [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")],
    ))
    assert result.status == "success"
    assert lines(out) == ["n", "11", "12", "13"]


def test_result_reports_the_rows_each_sink_wrote(tmp_path):
    result = run(job(
        [("in", "rows", {"data": {"n": [1, 2, 3]}}), ("out", "save", {"path": str(tmp_path / "o.csv")})],
        [("r1", "in", "out", "flow")],
    ))
    assert result.rows == {"out": 3}
    assert result.global_map["out_NB_LINE"] == 3


def test_one_output_can_feed_two_consumers(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    run(job(
        [("in", "rows", {"data": {"n": [1, 2]}}), ("add", "add", {"amount": 5}),
         ("a", "save", {"path": str(a)}), ("b", "save", {"path": str(b)})],
        [("r1", "in", "a", "flow"), ("r2", "in", "add", "flow"), ("r3", "add", "b", "flow")],
    ))
    assert lines(a) == ["n", "1", "2"]
    assert lines(b) == ["n", "6", "7"]


def test_every_row_leaves_by_exactly_one_port(tmp_path):
    kept, rejected = tmp_path / "kept.csv", tmp_path / "rejected.csv"
    result = run(job(
        [("in", "rows", {"data": {"n": [5, 1, 9, 2]}}), ("split", "split", {"limit": 4}),
         ("kept", "save", {"path": str(kept)}), ("rejected", "save", {"path": str(rejected)})],
        [("r1", "in", "split", "flow"), ("ok", "split", "kept", "filter"), ("bad", "split", "rejected", "reject")],
    ))
    assert lines(kept) == ["n", "5", "9"]
    assert lines(rejected) == ["n", "1", "2"]
    assert result.rows == {"kept": 2, "rejected": 2}


def test_inputs_reach_a_component_in_the_order_their_flows_are_written(tmp_path):
    out = tmp_path / "out.csv"
    components = [
        ("a", "rows", {"data": {"n": [1]}}), ("b", "rows", {"data": {"n": [2]}}),
        ("c", "rows", {"data": {"n": [3]}}), ("stack", "stack", {}), ("out", "save", {"path": str(out)}),
    ]
    flows = [("zz", "c", "stack", "flow"), ("mm", "a", "stack", "flow"), ("aa", "b", "stack", "flow"),
             ("r", "stack", "out", "flow")]
    run(job(components, flows))
    assert lines(out) == ["n,via", "3,zz", "1,mm", "2,aa"]


def test_two_outputs_of_one_component_can_meet_again(tmp_path):
    out = tmp_path / "out.csv"
    run(job(
        [("in", "rows", {"data": {"n": [5, 1]}}), ("split", "split", {"limit": 4}),
         ("stack", "stack", {}), ("out", "save", {"path": str(out)})],
        [("r1", "in", "split", "flow"), ("ok", "split", "stack", "filter"),
         ("bad", "split", "stack", "reject"), ("r2", "stack", "out", "flow")],
    ))
    assert lines(out) == ["n,via", "5,ok", "1,bad"]


def test_eager_component_is_handed_real_rows_and_the_plan_continues(tmp_path):
    Peek.seen.clear()
    out = tmp_path / "out.csv"
    run(job(
        [("in", "rows", {"data": {"n": [1, 2]}}), ("peek", "peek", {}), ("add", "add", {"amount": 1}),
         ("out", "save", {"path": str(out)})],
        [("r1", "in", "peek", "flow"), ("r2", "peek", "add", "flow"), ("r3", "add", "out", "flow")],
    ))
    assert len(Peek.seen) == 1
    assert isinstance(Peek.seen[0], pl.DataFrame)
    assert Peek.seen[0]["n"].to_list() == [1, 2]
    assert lines(out) == ["n", "2", "3"]


def test_output_nobody_reads_is_not_an_error(tmp_path):
    result = run(job(
        [("in", "rows", {"data": {"n": [5, 1]}}), ("split", "split", {"limit": 4}),
         ("kept", "save", {"path": str(tmp_path / "k.csv")})],
        [("r1", "in", "split", "flow"), ("ok", "split", "kept", "filter")],
    ))
    assert result.status == "success"


# ------------------------------------------------------------------
# Failure
# ------------------------------------------------------------------

def test_failure_names_the_component_and_leaves_no_output_behind(tmp_path):
    out = tmp_path / "out.csv"
    result = run(job(
        [("in", "rows", {"data": {"n": [1]}}), ("add", "add", {"column": "missing"}),
         ("out", "save", {"path": str(out)})],
        [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")],
    ))
    assert result.status == "failed"
    assert result.failed_component == "add"
    assert "missing" in result.error
    assert not out.exists()


def test_raise_for_status_raises_on_a_failed_job_only(tmp_path):
    good = run(job([("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": str(tmp_path / "o.csv")})],
                   [("r1", "in", "out", "flow")]))
    good.raise_for_status()
    bad = run(job([("in", "rows", {"data": {"n": [1]}}), ("add", "add", {"column": "missing"}),
                   ("out", "save", {"path": str(tmp_path / "p.csv")})],
                  [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")]))
    with pytest.raises(JobFailedError, match="add"):
        bad.raise_for_status()


def test_bad_data_in_a_lazy_source_is_blamed_on_the_source(tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("n\n1\nnot_a_number\n")
    out = tmp_path / "out.csv"

    class Typed(Source):
        names = ("typed",)
        keys = (Key("path", required=True),)

        def read(self):
            return {"main": pl.scan_csv(self.config["path"], schema={"n": pl.Int64})}

    registry = Registry()
    for cls in (Typed, Add, Save):
        registry.register(cls)
    result = run_job(job(
        [("in", "typed", {"path": str(source)}), ("add", "add", {}), ("out", "save", {"path": str(out)})],
        [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")],
    ), registry=registry)
    assert result.status == "failed"
    assert result.failed_component == "in"
    assert not out.exists()


# ------------------------------------------------------------------
# Several subjobs, context
# ------------------------------------------------------------------

def test_subjobs_run_in_job_config_order(tmp_path):
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    result = run(job(
        [("a_in", "rows", {"data": {"n": [1]}}), ("a_out", "save", {"path": str(first)}),
         ("b_in", "from_file", {"path": str(first)}), ("b_add", "add", {"amount": 1}),
         ("b_out", "save", {"path": str(second)})],
        [("r1", "a_in", "a_out", "flow"), ("r2", "b_in", "b_add", "flow"), ("r3", "b_add", "b_out", "flow")],
    ))
    assert result.status == "success"
    assert lines(second) == ["n", "2"]


def test_config_reads_context_values_set_earlier_in_the_run(tmp_path):
    out = tmp_path / "out.csv"
    result = run(job(
        [("vars", "rows", {"data": {"where": [str(out)]}}), ("set", "set_context", {}),
         ("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": "${context.where}"})],
        [("r0", "vars", "set", "flow"), ("r1", "in", "out", "flow")],
    ))
    assert result.status == "success"
    assert lines(out) == ["n", "1"]


def test_context_given_at_run_time_overrides_the_job_config(tmp_path):
    out = tmp_path / "out.csv"
    made = job(
        [("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": "${context.where}"})],
        [("r1", "in", "out", "flow")],
        context={"where": "nowhere.csv"},
    )
    run(made, context={"where": str(out)})
    assert lines(out) == ["n", "1"]


def test_unknown_context_variable_in_a_config_is_refused_before_anything_runs(tmp_path):
    with pytest.raises(JobRefusedError) as caught:
        run(job(
            [("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": "${context.nope}/o.csv"})],
            [("r1", "in", "out", "flow")],
        ))
    assert "context has no variable 'nope'" in caught.value.report.format()


def test_context_variable_nothing_ever_sets_fails_the_component_that_reads_it(tmp_path):
    # With a component that sets context while the job runs, the check at load cannot tell.
    result = run(job(
        [("vars", "rows", {"data": {"other": ["x"]}}), ("set", "set_context", {}),
         ("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": "${context.nope}/o.csv"})],
        [("r0", "vars", "set", "flow"), ("r1", "in", "out", "flow")],
    ))
    assert result.status == "failed"
    assert result.failed_component == "out"
    assert "nope" in result.error


# ------------------------------------------------------------------
# Refusals at load
# ------------------------------------------------------------------

def test_refused_job_config_is_raised_before_anything_runs(tmp_path):
    out = tmp_path / "out.csv"
    with pytest.raises(JobRefusedError):
        run(job([("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": str(out), "bogus": 1})],
                [("r1", "in", "out", "flow")]))
    assert not out.exists()


def test_flows_that_form_a_loop_are_refused():
    with pytest.raises(JobRefusedError) as caught:
        run(job([("a", "add", {}), ("b", "add", {})], [("r1", "a", "b", "flow"), ("r2", "b", "a", "flow")]))
    assert "loop" in caught.value.report.format()
